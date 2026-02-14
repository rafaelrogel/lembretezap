"""Tests for WhatsApp channel: chats only, never groups."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from zapista.channels.whatsapp import WhatsAppChannel
from zapista.config.schema import WhatsAppConfig


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


def test_is_allowed_audio():
    """allow_from_audio: vazio = todos podem; não vazio = só os da lista."""
    config_empty = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=["351912345678"], allow_from_audio=[])
    config_with = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=["351912345678"], allow_from_audio=["351912345678"])
    config_restrict = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=["351912345678"], allow_from_audio=["351999999999"])
    bus = MagicMock()
    ch_empty = WhatsAppChannel(config_empty, bus)
    ch_with = WhatsAppChannel(config_with, bus)
    ch_restrict = WhatsAppChannel(config_restrict, bus)
    assert ch_empty.is_allowed("351912345678") is True
    assert ch_empty.is_allowed_audio("351912345678") is True  # vazio = todos
    assert ch_with.is_allowed_audio("351912345678") is True   # na lista
    assert ch_restrict.is_allowed_audio("351912345678") is False  # não na lista


def test_is_allowed_tts():
    """allow_from_tts: vazio = todos podem receber TTS; não vazio = só os da lista."""
    config_empty = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=["351912345678"], allow_from_tts=[])
    config_with = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=["351912345678"], allow_from_tts=["351912345678"])
    config_restrict = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=["351912345678"], allow_from_tts=["351999999999"])
    bus = MagicMock()
    ch_empty = WhatsAppChannel(config_empty, bus)
    ch_with = WhatsAppChannel(config_with, bus)
    ch_restrict = WhatsAppChannel(config_restrict, bus)
    assert ch_empty.is_allowed_tts("351912345678") is True  # vazio = todos
    assert ch_empty.is_allowed_tts("351912345678@s.whatsapp.net") is True
    assert ch_with.is_allowed_tts("351912345678") is True   # na lista
    assert ch_restrict.is_allowed_tts("351912345678") is False  # não na lista
