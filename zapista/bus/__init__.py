"""Message bus module for decoupled channel-agent communication."""

from zapista.bus.events import InboundMessage, OutboundMessage
from zapista.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
