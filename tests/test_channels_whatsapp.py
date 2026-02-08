"""Tests for WhatsApp channel: chats only, never groups."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure repo root on path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nanobot.channels.whatsapp import WhatsAppChannel
from nanobot.config.schema import WhatsAppConfig


@pytest.fixture
def wa_config():
    return WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=[])


@pytest.fixture
def channel(wa_config):
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    return WhatsAppChannel(wa_config, bus)


@pytest.mark.asyncio
async def test_group_message_ignored(channel):
    """Messages from groups must not be forwarded to the bus."""
    raw = json.dumps({
        "type": "message",
        "sender": "120363xxx@g.us",
        "content": "oi",
        "isGroup": True,
    })
    await channel._handle_bridge_message(raw)
    channel.bus.publish_inbound.assert_not_called()


@pytest.mark.asyncio
async def test_group_message_by_jid_suffix_ignored(channel):
    """Messages with sender ending in @g.us are ignored even without isGroup."""
    raw = json.dumps({
        "type": "message",
        "sender": "120363123456789@g.us",
        "content": "hello",
        "isGroup": False,
    })
    await channel._handle_bridge_message(raw)
    channel.bus.publish_inbound.assert_not_called()


@pytest.mark.asyncio
async def test_chat_message_forwarded(channel):
    """Private chat messages are forwarded to the bus."""
    raw = json.dumps({
        "type": "message",
        "sender": "5511999999999@s.whatsapp.net",
        "content": "lembrete em 2 min",
    })
    await channel._handle_bridge_message(raw)
    channel.bus.publish_inbound.assert_called_once()
    call = channel.bus.publish_inbound.call_args[0][0]
    assert call.channel == "whatsapp"
    assert call.chat_id == "5511999999999@s.whatsapp.net"
    assert "lembrete" in call.content
    assert call.metadata.get("is_group") is False
