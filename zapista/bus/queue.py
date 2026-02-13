"""Async message queue for decoupled channel-agent communication.

Com Redis (REDIS_URL): outbound vai para a fila Redis; um feeder task
drena Redis para a queue local; o dispatch envia como antes.
Sem Redis: outbound vai só para a queue in-memory.
"""

import asyncio
import os
from typing import Callable, Awaitable

from loguru import logger

from zapista.bus.events import InboundMessage, OutboundMessage


def _redis_url_from_env() -> str | None:
    u = os.environ.get("REDIS_URL", "").strip()
    return u or None


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.
    
    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    When REDIS_URL is set, outbound is pushed to Redis and a feeder task
    drains Redis into the local outbound queue for dispatch.
    """
    
    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or _redis_url_from_env()
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_subscribers: dict[str, list[Callable[[OutboundMessage], Awaitable[None]]]] = {}
        self._running = False
        self._redis_feeder_task: asyncio.Task | None = None
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        await self.inbound.put(msg)
    
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
        """Stop the dispatcher loop and Redis feeder."""
        self._running = False
        if self._redis_feeder_task and not self._redis_feeder_task.done():
            self._redis_feeder_task.cancel()

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
