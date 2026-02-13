"""Channel manager for coordinating chat channels (chats only; no groups).
Deduplicação de envio evita que o mesmo texto seja enviado várias vezes ao mesmo chat (ex.: 37 mensagens iguais).
"""

import asyncio
import hashlib
import time
from typing import Any

from loguru import logger

from zapista.bus.events import OutboundMessage
from zapista.bus.queue import MessageBus
from zapista.channels.base import BaseChannel
from zapista.config.schema import Config

_OUTBOUND_DEDUP_SECONDS = 90
_sent_recently: dict[tuple[str, str, str], float] = {}  # (channel, chat_id, content_hash) -> timestamp


def _outbound_dedup_key(msg: OutboundMessage) -> tuple[str, str, str]:
    h = hashlib.sha256(msg.content.encode("utf-8", errors="replace")).hexdigest()[:16]
    return (msg.channel, str(msg.chat_id), h)


def _should_skip_duplicate_outbound(msg: OutboundMessage) -> bool:
    """True se já enviamos esta mesma mensagem (canal + chat + conteúdo) recentemente."""
    now = time.time()
    key = _outbound_dedup_key(msg)
    # Limpar entradas antigas
    to_del = [k for k, t in _sent_recently.items() if now - t > _OUTBOUND_DEDUP_SECONDS]
    for k in to_del:
        del _sent_recently[k]
    if key in _sent_recently:
        return True
    _sent_recently[key] = now
    return False


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.
    WhatsApp only; we respond in private chats and never in groups.
    """
    
    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        
        self._init_channels()
    
    def _init_channels(self) -> None:
        """Initialize channels based on config (WhatsApp only)."""
        if self.config.channels.whatsapp.enabled:
            try:
                from zapista.channels.whatsapp import WhatsAppChannel
                self.channels["whatsapp"] = WhatsAppChannel(
                    self.config.channels.whatsapp, self.bus
                )
                logger.info("WhatsApp channel enabled")
            except ImportError as e:
                logger.warning(f"WhatsApp channel not available: {e}")
    
    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """Start a channel and log any exceptions."""
        try:
            await channel.start()
        except Exception as e:
            logger.error(f"Failed to start channel {name}: {e}")

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return
        
        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())
        
        # Start channels
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            tasks.append(asyncio.create_task(self._start_channel(name, channel)))
        
        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")
        
        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        
        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
    
    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")
        
        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )
                
                # Evitar enviar a mesma mensagem muitas vezes ao mesmo chat (ex.: 37 iguais)
                if _should_skip_duplicate_outbound(msg):
                    logger.debug(f"Skip duplicate outbound to {msg.channel}:{str(msg.chat_id)[:25]}... (same content recently)")
                    continue
                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        logger.info(f"Dispatch outbound: channel={msg.channel} chat_id={str(msg.chat_id)[:25]}...")
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Unknown channel: {msg.channel} (message not delivered; enable WhatsApp and add reminder from WhatsApp)")
                    try:
                        from backend.server_metrics import record_event
                        record_event("unknown_channel")
                    except Exception:
                        pass
                    
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)
    
    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }
    
    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
