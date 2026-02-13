"""Stress tests for voice message flow: transcription, guardrails, i18n."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zapista.channels.whatsapp import WhatsAppChannel
from zapista.config.schema import WhatsAppConfig


def _make_channel(allow_from=None, allow_from_audio=None):
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    bus.publish_outbound = AsyncMock()
    config = WhatsAppConfig(
        enabled=True,
        bridge_url="ws://localhost:3001",
        allow_from=allow_from or [],
        allow_from_audio=allow_from_audio or [],
    )
    return WhatsAppChannel(config, bus)


from contextlib import contextmanager


@contextmanager
def _mock_db_and_lang(user_lang="pt-BR"):
    """Context manager to mock DB and lang resolution."""
    mock_session = MagicMock()
    with (
        patch("backend.database.SessionLocal", return_value=mock_session),
        patch("backend.user_store.get_user_language", return_value=user_lang),
        patch("backend.locale.phone_to_default_language", return_value=user_lang),
    ):
        yield


# --- audioTooLarge ---
@pytest.mark.asyncio
async def test_voice_audio_too_large_sends_localized_message():
    """Quando bridge envia audioTooLarge, gateway responde com mensagem no idioma do cliente."""
    channel = _make_channel(allow_from_audio=[])  # vazio = todos
    with _mock_db_and_lang("pt-PT"):
        raw = json.dumps({
            "type": "message",
            "id": "v1",
            "sender": "351912345678@s.whatsapp.net",
            "pn": "351912345678",
            "content": "[Voice Message]",
            "timestamp": 1739123456,
            "isGroup": False,
            "audioTooLarge": True,
        })
        await channel._handle_bridge_message(raw)
    channel.bus.publish_outbound.assert_called_once()
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "longo" in out.content or "curta" in out.content
    channel.bus.publish_inbound.assert_not_called()


@pytest.mark.asyncio
async def test_voice_audio_too_large_english():
    """audioTooLarge com user en → mensagem em inglês."""
    channel = _make_channel(allow_from_audio=[])
    with _mock_db_and_lang("en"):
        raw = json.dumps({
            "type": "message", "id": "v2", "sender": "447911123456@s.whatsapp.net",
            "pn": "447911123456", "content": "[Voice Message]", "timestamp": 1739123456,
            "isGroup": False, "audioTooLarge": True,
        })
        await channel._handle_bridge_message(raw)
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "audio" in out.content.lower() and "shorter" in out.content.lower()


# --- audioForwarded ---
@pytest.mark.asyncio
async def test_voice_forwarded_rejected():
    """Áudio reencaminhado → mensagem de rejeição, não transcreve."""
    channel = _make_channel(allow_from_audio=[])
    with _mock_db_and_lang("pt-BR"):
        raw = json.dumps({
            "type": "message", "id": "v3", "sender": "5511999999999@s.whatsapp.net",
            "pn": "5511999999999", "content": "[Voice Message]", "timestamp": 1739123456,
            "isGroup": False, "audioForwarded": True,
        })
        await channel._handle_bridge_message(raw)
    channel.bus.publish_outbound.assert_called_once()
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "gravado" in out.content or "encaminhe" in out.content or "forward" in out.content.lower()
    channel.bus.publish_inbound.assert_not_called()


# --- allow_from_audio (restrito) ---
@pytest.mark.asyncio
async def test_voice_not_allowed_audio_sender_rejected():
    """Utilizador fora de allow_from_audio recebe AUDIO_NOT_ALLOWED."""
    channel = _make_channel(allow_from=["351111"], allow_from_audio=["351999"])  # só 351999 pode áudio
    with _mock_db_and_lang("pt-PT"):
        raw = json.dumps({
            "type": "message", "id": "v4", "sender": "351111222333@s.whatsapp.net",
            "pn": "351111222333", "content": "[Voice Message]", "timestamp": 1739123456,
            "isGroup": False, "mediaBase64": "aGVsbG8=",  # base64 "hello"
        })
        await channel._handle_bridge_message(raw)
    channel.bus.publish_outbound.assert_called_once()
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "disponível" in out.content or "available" in out.content.lower()
    channel.bus.publish_inbound.assert_not_called()


# --- duration too long (AUDIO_TOO_LONG) ---
@pytest.mark.asyncio
async def test_voice_duration_too_long_rejected():
    """Áudio > 60s → check_audio_duration retorna AUDIO_TOO_LONG, mensagem localizada."""
    channel = _make_channel(allow_from_audio=[])
    with _mock_db_and_lang("es"):
        with patch("zapista.stt.audio_utils.check_audio_duration", return_value="AUDIO_TOO_LONG"):
            raw = json.dumps({
                "type": "message", "id": "v5", "sender": "34612345678@s.whatsapp.net",
                "pn": "34612345678", "content": "[Voice Message]", "timestamp": 1739123456,
                "isGroup": False, "mediaBase64": "dGVzdA==",
            })
            await channel._handle_bridge_message(raw)
    channel.bus.publish_outbound.assert_called_once()
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "audio" in out.content.lower() or "mensaje" in out.content.lower() or "corto" in out.content.lower()
    channel.bus.publish_inbound.assert_not_called()


# --- transcribe failed ---
@pytest.mark.asyncio
async def test_voice_transcribe_failed_sends_error():
    """Transcrição falha → AUDIO_TRANSCRIBE_FAILED (não envia ao agente)."""
    channel = _make_channel(allow_from_audio=[])
    with _mock_db_and_lang("pt-BR"):
        with patch("zapista.stt.audio_utils.check_audio_duration", return_value=None):
            with patch("zapista.stt.transcribe", new_callable=AsyncMock, return_value=""):
                raw = json.dumps({
                    "type": "message", "id": "v6", "sender": "5511988887777@s.whatsapp.net",
                    "pn": "5511988887777", "content": "[Voice Message]", "timestamp": 1739123456,
                    "isGroup": False, "mediaBase64": "dGVzdA==",
                })
                await channel._handle_bridge_message(raw)
    channel.bus.publish_outbound.assert_called_once()
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "transcrever" in out.content or "transcribe" in out.content.lower()
    channel.bus.publish_inbound.assert_not_called()


# --- transcribe success: content forwarded to agent ---
@pytest.mark.asyncio
async def test_voice_transcribe_success_forwards_to_agent():
    """Transcrição OK → content = texto transcrito, enviado ao agente (publish_inbound)."""
    channel = _make_channel(allow_from_audio=[])
    with _mock_db_and_lang("en"):
        with patch("zapista.stt.audio_utils.check_audio_duration", return_value=None):
            with patch("zapista.stt.transcribe", new_callable=AsyncMock, return_value="remind me in 5 minutes"):
                raw = json.dumps({
                    "type": "message", "id": "v7", "sender": "447700000001@s.whatsapp.net",
                    "pn": "447700000001", "content": "[Voice Message]", "timestamp": 1739123456,
                    "isGroup": False, "mediaBase64": "cmVtaW5k",
                })
                await channel._handle_bridge_message(raw)
    channel.bus.publish_inbound.assert_called_once()
    inbound = channel.bus.publish_inbound.call_args[0][0]
    assert inbound.content == "remind me in 5 minutes"
    assert inbound.channel == "whatsapp"


# --- no mediaBase64 (download failed) ---
@pytest.mark.asyncio
async def test_voice_no_mediabase64_sends_not_received():
    """Áudio sem mediaBase64 (download falhou) → AUDIO_NOT_RECEIVED."""
    channel = _make_channel(allow_from_audio=[])
    with _mock_db_and_lang("pt-PT"):
        raw = json.dumps({
            "type": "message", "id": "v8", "sender": "351987654321@s.whatsapp.net",
            "pn": "351987654321", "content": "[Voice Message]", "timestamp": 1739123456,
            "isGroup": False,
        })
        await channel._handle_bridge_message(raw)
    channel.bus.publish_outbound.assert_called_once()
    out = channel.bus.publish_outbound.call_args[0][0]
    assert "recebido" in out.content or "received" in out.content.lower()
    channel.bus.publish_inbound.assert_not_called()


# --- STT module: audio_utils ---
def test_audio_utils_check_duration_invalid_base64():
    """check_audio_duration com base64 inválido retorna None (decode falha)."""
    from zapista.stt.audio_utils import check_audio_duration
    result = check_audio_duration("invalid!!!")
    assert result is None


def test_audio_utils_decode_base64():
    """decode_base64_to_temp com base64 válido cria ficheiro."""
    from zapista.stt.audio_utils import decode_base64_to_temp
    path = decode_base64_to_temp("aGVsbG8gd29ybGQ=")  # "hello world"
    assert path is not None
    if path:
        try:
            assert path.exists()
            assert path.read_bytes() == b"hello world"
        finally:
            path.unlink(missing_ok=True)


def test_audio_utils_decode_invalid_returns_none():
    """decode_base64_to_temp com base64 inválido retorna None."""
    from zapista.stt.audio_utils import decode_base64_to_temp
    assert decode_base64_to_temp("!!!") is None


# --- locale: audio messages in 4 languages ---
def test_locale_audio_messages_all_langs():
    """Mensagens de áudio existem nos 4 idiomas."""
    from backend.locale import (
        AUDIO_FORWARDED,
        AUDIO_NOT_ALLOWED,
        AUDIO_NOT_RECEIVED,
        AUDIO_TOO_LONG,
        AUDIO_TRANSCRIBE_FAILED,
    )
    for key in (AUDIO_FORWARDED, AUDIO_NOT_ALLOWED, AUDIO_NOT_RECEIVED, AUDIO_TOO_LONG, AUDIO_TRANSCRIBE_FAILED):
        assert "pt-PT" in key
        assert "pt-BR" in key
        assert "es" in key
        assert "en" in key
        for lang in ("pt-PT", "pt-BR", "es", "en"):
            assert len(key[lang]) > 5
