"""WhatsApp channel implementation using Node.js bridge.

We only handle private chats. We never respond in groups: messages from groups
are ignored and not forwarded to the agent.
Deduplicação por message_id evita processar o mesmo evento várias vezes (bridge/Baileys pode reenviar).
"""

import asyncio
import json
import time
import uuid
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import WhatsAppConfig

# JID suffix for WhatsApp groups; we only process chats (e.g. @s.whatsapp.net or LID), never groups
WHATSAPP_GROUP_SUFFIX = "@g.us"

# Dedup: ignorar mensagens com o mesmo message_id já processado nos últimos N segundos
_DEDUP_SECONDS = 120
_processed_ids: dict[str, float] = {}
# Fallback quando o bridge não envia id: dedup por (chat_id, conteúdo, janela 30s)
_processed_fallback: dict[tuple[str, str, int], float] = {}
_FALLBACK_BUCKET_SECONDS = 30


def _is_duplicate_message(msg_id: str) -> bool:
    """True se esta mensagem já foi processada recentemente (evita chamadas LLM duplicadas)."""
    if not msg_id:
        return False
    now = time.time()
    to_del = [k for k, t in _processed_ids.items() if now - t > _DEDUP_SECONDS]
    for k in to_del:
        del _processed_ids[k]
    if msg_id in _processed_ids:
        return True
    _processed_ids[msg_id] = now
    return False


def _is_duplicate_by_content(chat_id: str, content: str) -> bool:
    """Fallback quando não há message_id: mesmo chat + mesmo texto na mesma janela = duplicado."""
    if not content and not chat_id:
        return False
    now = time.time()
    bucket = int(now / _FALLBACK_BUCKET_SECONDS)
    key = (chat_id, content.strip()[:200], bucket)
    to_del = [k for k, t in _processed_fallback.items() if now - t > _DEDUP_SECONDS]
    for k in to_del:
        del _processed_fallback[k]
    if key in _processed_fallback:
        return True
    _processed_fallback[key] = now
    return False


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp channel that connects to a Node.js bridge.
    Chats only: we respond in private chats and never in groups.
    The bridge uses @whiskeysockets/baileys; communication is via WebSocket.
    """
    
    name = "whatsapp"
    
    def __init__(self, config: WhatsAppConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self._ws = None
        self._connected = False
        self._cron_tool = None  # opcional: para lembretes 15 min antes de eventos .ics

    def set_ics_cron_tool(self, cron_tool) -> None:
        """Injetar CronTool para criar lembretes 15 min antes de cada evento ao importar .ics."""
        self._cron_tool = cron_tool

    async def start(self) -> None:
        """Start the WhatsApp channel by connecting to the bridge."""
        import websockets
        
        bridge_url = self.config.bridge_url
        
        logger.info(f"Connecting to WhatsApp bridge at {bridge_url}...")
        
        self._running = True
        
        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info("Connected to WhatsApp bridge")
                    
                    # Listen for messages
                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            logger.error(f"Error handling bridge message: {e}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(f"WhatsApp bridge connection error: {e}")
                
                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        self._running = False
        self._connected = False
        
        if self._ws:
            await self._ws.close()
            self._ws = None
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WhatsApp."""
        if not self._ws or not self._connected:
            logger.warning("WhatsApp send skipped: bridge not connected")
            return
        
        try:
            payload = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content
            }
            logger.info(f"WhatsApp send: to={str(msg.chat_id)[:30]}... len={len(msg.content)}")
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
    
    async def _handle_bridge_message(self, raw: str) -> None:
        """Handle a message from the bridge."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from bridge: {raw[:100]}")
            return
        
        msg_type = data.get("type")
        
        if msg_type == "message":
            # Evitar processar o mesmo evento várias vezes (reduz chamadas LLM duplicadas)
            msg_id = (data.get("id") or "").strip()
            if _is_duplicate_message(msg_id):
                logger.debug(f"Ignoring duplicate message id={msg_id!r}")
                return

            # Incoming message from WhatsApp — we only process chats, never groups
            is_group = data.get("isGroup", False) or (data.get("sender") or "").strip().endswith(WHATSAPP_GROUP_SUFFIX)
            if is_group:
                logger.debug("Ignoring message from group (we only respond in private chats)")
                return

            # Deprecated by whatsapp: old phone number style typically: <phone>@s.whatsapp.net
            pn = data.get("pn", "")
            # New LID style typically:
            sender = data.get("sender", "")
            content = data.get("content", "")

            # Fallback dedup quando o bridge não envia id: mesmo chat + mesmo texto em 30s = ignorar
            if not msg_id and _is_duplicate_by_content(sender, content or ""):
                logger.debug(f"Ignoring duplicate by content from {sender[:20]}...")
                return

            # Extract just the phone number or lid as chat_id
            user_id = pn if pn else sender
            sender_id = user_id.split("@")[0] if "@" in user_id else user_id
            # Se um tester não receber resposta, ver nos logs este valor e adiciona-o a allow_from no config
            logger.info(f"WhatsApp from sender={sender!r} → sender_id={sender_id!r} (use na allow_from se bloqueado)")

            # Handle voice transcription if it's a voice message
            if content == "[Voice Message]":
                logger.info(f"Voice message received from {sender_id}, but direct download from bridge is not yet supported.")
                content = "[Voice Message: Transcription not available for WhatsApp yet]"

            # Anexo .ics: parse e registar eventos (sem passar ao agente)
            attachment_ics = data.get("attachmentIcs") or data.get("attachment_ics")
            if attachment_ics and isinstance(attachment_ics, str) and attachment_ics.strip():
                from nanobot.bus.events import OutboundMessage
                try:
                    from backend.ics_handler import handle_ics_payload
                    from backend.database import SessionLocal
                    response = await handle_ics_payload(
                        chat_id=sender,
                        sender_id=sender_id,
                        ics_content=attachment_ics.strip(),
                        db_session_factory=SessionLocal,
                        cron_tool=getattr(self, "_cron_tool", None),
                        cron_channel=self.name,
                    )
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content=response or "—",
                    ))
                except Exception as e:
                    logger.exception(f"ICS handler failed: {e}")
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content="Erro ao processar o calendário. Tenta outro ficheiro .ics.",
                    ))
                return

            # God Mode: #<senha> ativa; #cmd só se já ativou. Senha errada ou #inválido = silêncio.
            if (content or "").strip().startswith("#"):
                from backend.admin_commands import (
                    is_god_mode_password,
                    is_god_mode_activated,
                    activate_god_mode,
                    parse_admin_command,
                    handle_admin_command,
                )
                from nanobot.bus.events import OutboundMessage
                raw = (content or "").strip()
                rest = raw[1:].strip()  # texto após #
                if is_god_mode_password(rest):
                    activate_god_mode(sender)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=self.name,
                        chat_id=sender,
                        content="God-mode ativo. Comandos: #status #users #cron #server #system #ai #painpoints",
                    ))
                    return
                cmd = parse_admin_command(raw)
                if cmd and is_god_mode_activated(sender):
                    try:
                        from backend.database import SessionLocal
                        from pathlib import Path
                        cron_path = Path.home() / ".nanobot" / "cron" / "jobs.json"
                        response = await handle_admin_command(
                            raw,
                            db_session_factory=SessionLocal,
                            cron_store_path=cron_path,
                        )
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=sender,
                            content=response or "—",
                        ))
                    except Exception as e:
                        logger.exception(f"Admin command failed: {e}")
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=self.name,
                            chat_id=sender,
                            content="Erro ao executar comando admin.",
                        ))
                    return
                # Senha errada ou #qualquer_outra_coisa sem god-mode ativo: não responder (silêncio)
                return

            # Forward to agent only for private chats (groups already filtered above)
            trace_id = uuid.uuid4().hex[:12]
            await self._handle_message(
                sender_id=sender_id,
                chat_id=sender,  # Use full JID/LID for replies
                content=content,
                metadata={
                    "message_id": data.get("id"),
                    "timestamp": data.get("timestamp"),
                    "is_group": False,
                    "trace_id": trace_id,
                },
            )
        
        elif msg_type == "status":
            # Connection status update
            status = data.get("status")
            logger.info(f"WhatsApp status: {status}")
            
            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False
        
        elif msg_type == "qr":
            # QR code for authentication
            logger.info("Scan QR code in the bridge terminal to connect WhatsApp")
        
        elif msg_type == "error":
            logger.error(f"WhatsApp bridge error: {data.get('error')}")
