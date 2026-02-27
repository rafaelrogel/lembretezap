"""Async message queue for decoupled channel-agent communication.

Com Redis (REDIS_URL): outbound vai para a fila Redis; um feeder task
drena Redis para a queue local; o dispatch envia como antes.
Sem Redis: outbound vai só para a queue in-memory.

Debounce (MSG_BUFFER_SECONDS, default 3):
  Mensagens do mesmo chat_id dentro da janela são acumuladas e entregues
  como uma única mensagem, evitando resposta item-a-item em rajadas.
  Comandos (começam com /) passam direto sem buffer.
"""

import asyncio
import os
from typing import Callable, Awaitable

from loguru import logger

from zapista.bus.events import InboundMessage, OutboundMessage


def _redis_url_from_env() -> str | None:
    u = os.environ.get("REDIS_URL", "").strip()
    return u or None


def _buffer_seconds() -> float:
    """Janela de debounce em segundos. MSG_BUFFER_SECONDS=0 desativa o buffer."""
    v = os.environ.get("MSG_BUFFER_SECONDS", "3").strip()
    try:
        return max(0.0, min(30.0, float(v)))
    except ValueError:
        return 3.0


def _buffer_max() -> int:
    """Número máximo de mensagens a acumular por janela (anti-spam)."""
    v = os.environ.get("MSG_BUFFER_MAX", "10").strip()
    try:
        return max(1, min(50, int(v)))
    except ValueError:
        return 10


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.
    
    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    When REDIS_URL is set, outbound is pushed to Redis and a feeder task
    drains Redis into the local outbound queue for dispatch.

    Debounce: mensagens do mesmo chat_id dentro da janela MSG_BUFFER_SECONDS
    são acumuladas e entregues como uma única mensagem ao agente.
    """
    
    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or _redis_url_from_env()
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_subscribers: dict[str, list[Callable[[OutboundMessage], Awaitable[None]]]] = {}
        self._running = False
        self._redis_feeder_task: asyncio.Task | None = None
        # Debounce state (per chat_id)
        self._pending: dict[str, InboundMessage] = {}
        self._pending_tasks: dict[str, asyncio.Task] = {}

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent, with debounce buffering."""
        delay = _buffer_seconds()
        content = (msg.content or "").strip()

        # Comandos passam direto (sem buffer) para não atrasar /feito, /start, etc.
        is_command = content.startswith("/")

        if delay <= 0 or is_command:
            await self.inbound.put(msg)
            return

        key = f"{msg.channel}:{msg.chat_id}"
        max_msgs = _buffer_max()

        # Cancelar task anterior se existir
        existing_task = self._pending_tasks.pop(key, None)
        if existing_task and not existing_task.done():
            existing_task.cancel()

        # Acumular conteúdo no pending
        if key in self._pending:
            prev = self._pending[key]
            count = prev.metadata.get("_buffer_count", 1)
            if count < max_msgs:
                # Juntar conteúdo com nova linha (natural para o LLM)
                joined = (prev.content or "").rstrip() + "\n" + content
                # Manter metadata do primeiro msg + atualizar com último
                merged_meta = dict(prev.metadata)
                merged_meta.update(msg.metadata)
                merged_meta["_buffer_count"] = count + 1
                self._pending[key] = InboundMessage(
                    channel=msg.channel,
                    sender_id=msg.sender_id,
                    chat_id=msg.chat_id,
                    content=joined,
                    timestamp=msg.timestamp,
                    media=prev.media + msg.media,
                    metadata=merged_meta,
                    trace_id=msg.trace_id or prev.trace_id,
                )
            # Se atingiu max_msgs, descarta as novas (já vai processar em breve)
        else:
            self._pending[key] = msg

        # Iniciar novo timer
        async def _flush(k: str) -> None:
            await asyncio.sleep(delay)
            buffered = self._pending.pop(k, None)
            self._pending_tasks.pop(k, None)
            if buffered:
                count = buffered.metadata.get("_buffer_count", 1)
                if count > 1:
                    logger.debug(f"Buffer flush: {k} acumulou {count} msgs → 1 entrega")
                await self.inbound.put(buffered)

        task = asyncio.create_task(_flush(key))
        self._pending_tasks[key] = task

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()
    
    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels (local queue or Redis)."""
        if self.redis_url:
            try:
                from zapista.bus.redis_queue import push_outbound
                if await push_outbound(self.redis_url, msg):
                    return
            except Exception as e:
                logger.warning(f"Redis push failed, falling back to local queue: {e}")
        await self.outbound.put(msg)
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()
    
    def subscribe_outbound(
        self, 
        channel: str, 
        callback: Callable[[OutboundMessage], Awaitable[None]]
    ) -> None:
        """Subscribe to outbound messages for a specific channel."""
        if channel not in self._outbound_subscribers:
            self._outbound_subscribers[channel] = []
        self._outbound_subscribers[channel].append(callback)
    
    async def dispatch_outbound(self) -> None:
        """
        Dispatch outbound messages to subscribed channels.
        Run this as a background task.
        """
        self._running = True
        while self._running:
            try:
                msg = await asyncio.wait_for(self.outbound.get(), timeout=1.0)
                subscribers = self._outbound_subscribers.get(msg.channel, [])
                for callback in subscribers:
                    try:
                        await callback(msg)
                    except Exception as e:
                        logger.error(f"Error dispatching to {msg.channel}: {e}")
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the dispatcher loop, Redis feeder, and cancel pending buffer tasks."""
        self._running = False
        if self._redis_feeder_task and not self._redis_feeder_task.done():
            self._redis_feeder_task.cancel()
        # Cancelar todos os timers de debounce pendentes (flush imediato no shutdown)
        for task in list(self._pending_tasks.values()):
            if not task.done():
                task.cancel()
        self._pending_tasks.clear()
        self._pending.clear()

    async def _redis_feeder_loop(self) -> None:
        """Drena a fila Redis para a queue local outbound (correr como task)."""
        if not self.redis_url:
            return
        from zapista.bus.redis_queue import pop_outbound_blocking
        logger.info("Redis outbound feeder started")
        try:
            while True:
                try:
                    msg = await pop_outbound_blocking(self.redis_url)
                    if msg:
                        await self.outbound.put(msg)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Redis feeder: {e}")
        finally:
            logger.info("Redis outbound feeder stopped")

    def start_redis_feeder(self) -> asyncio.Task | None:
        """Inicia o task que drena Redis para outbound. Retorna o task ou None."""
        if not self.redis_url:
            return None
        self._redis_feeder_task = asyncio.create_task(self._redis_feeder_loop())
        return self._redis_feeder_task
    
    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()
    
    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
