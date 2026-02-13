"""Chat channels module with plugin architecture."""

from zapista.channels.base import BaseChannel
from zapista.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
