"""Base channel interface for chat platforms."""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from zapista.bus.events import InboundMessage, OutboundMessage
from zapista.bus.queue import MessageBus


class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.
    
    Currently only WhatsApp is supported. New channels should implement
    this interface to integrate with the Zapista message bus.
    """
    
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageBus):
        """
        Initialize the channel.
        
        Args:
            config: Channel-specific configuration.
            bus: The message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.
        
        This should be a long-running async task that:
        1. Connects to the chat platform
        2. Listens for incoming messages
        3. Forwards messages to the bus via _handle_message()
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through this channel.
        
        Args:
            msg: The message to send.
        """
        pass
    
    def _normalize_digits(self, value: str) -> str:
        """Remove tudo exceto dígitos (para comparar números de telefone em formatos diferentes)."""
        return "".join(c for c in str(value) if c.isdigit())

    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if a sender is allowed to use this bot.
        Compara o identificador exato e também só os dígitos (ex.: 351912540117 = 351 912 540 117).
        Lista = allow_from (config) + números adicionados via #add (allowed_extra.json).
        """
        from zapista.utils.extra_allowed import get_extra_allowed_list
        allow_list = list(getattr(self.config, "allow_from", [])) + get_extra_allowed_list()
        
        if not allow_list:
            return True
        
        sender_str = str(sender_id).strip()
        sender_digits = self._normalize_digits(sender_str)

        if sender_str in allow_list:
            return True
        if sender_digits and any(sender_digits == self._normalize_digits(a) for a in allow_list if self._normalize_digits(a)):
            return True
        if "|" in sender_str:
            for part in sender_str.split("|"):
                part = part.strip()
                if part and (part in allow_list or (self._normalize_digits(part) and self._normalize_digits(part) == sender_digits)):
                    return True
        return False
    
    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Handle an incoming message from the chat platform.
        For WhatsApp we only process private chats; groups are ignored in the channel.
        This method checks permissions and forwards to the bus.
        Args:
            sender_id: The sender's identifier.
            chat_id: The chat/channel identifier (private chat only on WhatsApp).
            content: Message text content.
            media: Optional list of media URLs.
            metadata: Optional channel-specific metadata.
        """
        if not self.is_allowed(sender_id):
            logger.warning(
                f"Access denied for sender {sender_id} on channel {self.name}. "
                f"Add them to allowFrom list in config to grant access."
            )
            # Enviar resposta para o utilizador em vez de silêncio (assim sabe que está bloqueado)
            await self.bus.publish_outbound(OutboundMessage(
                channel=self.name,
                chat_id=str(chat_id),
                content="Não estás autorizado a usar este bot. O teu número tem de estar na lista do administrador. Se és o dono, adiciona este número em allow_from no config e reinicia o gateway.",
            ))
            return

        # Muted/penalidade: não responder (silêncio)
        from zapista.utils.muted_store import is_muted
        if is_muted(sender_id):
            return

        meta = metadata or {}
        trace_id = meta.get("trace_id")
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=meta,
            trace_id=trace_id,
        )

        await self.bus.publish_inbound(msg)
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running
