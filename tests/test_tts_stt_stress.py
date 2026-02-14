"""
Stress tests para TTS e STT.

TTS: voices, config, service (Piper mocked), audio conversion.
STT: transcribe (providers mocked), audio_utils.
"""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# TTS — voices
# =============================================================================


class TestTTSVoices:
    """Stress: resolve_locale_for_audio, get_voice_paths."""

    def test_resolve_locale_override_ptpt(self):
        from zapista.tts.voices import resolve_locale_for_audio

        for tok in ("ptpt", "pt-pt", "pt_pt"):
            assert resolve_locale_for_audio("351912345678@s.whatsapp.net", tok) == "pt-PT"

    def test_resolve_locale_override_ptbr(self):
        from zapista.tts.voices import resolve_locale_for_audio

        for tok in ("ptbr", "pt-br", "pt_br"):
            assert resolve_locale_for_audio("5511999999999@s.whatsapp.net", tok) == "pt-BR"

    def test_resolve_locale_override_es_en(self):
        from zapista.tts.voices import resolve_locale_for_audio

        assert resolve_locale_for_audio("x", "es") == "es"
        assert resolve_locale_for_audio("x", "en") == "en"
        assert resolve_locale_for_audio("x", "english") == "en"

    def test_resolve_locale_from_db(self):
        from zapista.tts.voices import resolve_locale_for_audio

        with patch("backend.user_store.get_user_language", return_value="pt-PT"):
            with patch("backend.database.SessionLocal", return_value=MagicMock()):
                with patch("backend.locale.phone_to_default_language", return_value="pt-BR"):
                    result = resolve_locale_for_audio("351912345678@s.whatsapp.net", None)
        assert result == "pt-PT"

    def test_resolve_locale_phone_fallback(self):
        from zapista.tts.voices import resolve_locale_for_audio

        with patch("backend.user_store.get_user_language", return_value=None):
            with patch("backend.database.SessionLocal", return_value=MagicMock()):
                with patch("backend.locale.phone_to_default_language", return_value="es"):
                    result = resolve_locale_for_audio("34612345678@s.whatsapp.net", None)
        assert result == "es"

    def test_get_voice_paths_no_models_returns_none(self):
        """Sem modelos instalados, get_voice_paths retorna (None, None)."""
        from zapista.tts.voices import get_voice_paths

        with patch.dict(os.environ, {"TTS_MODELS_BASE": tempfile.mkdtemp()}, clear=False):
            m, c = get_voice_paths("pt-BR")
        assert m is None or not Path(m).exists()
        assert c is None or not Path(c).exists()

    def test_get_voice_paths_fallback_locale(self):
        """Quando pt-PT não existe, fallback para pt-BR."""
        from zapista.tts.voices import get_voice_paths

        base = tempfile.mkdtemp()
        pt_br_model = Path(base) / "pt/pt_BR/cadu/medium"
        pt_br_model.mkdir(parents=True, exist_ok=True)
        (pt_br_model / "pt_BR-cadu-medium.onnx").touch()
        (pt_br_model / "pt_BR-cadu-medium.onnx.json").touch()

        with patch.dict(os.environ, {"TTS_MODELS_BASE": base}, clear=False):
            m, c = get_voice_paths("pt-PT")
        assert m is not None and Path(m).exists()
        assert "pt_BR" in str(m)
        assert c is not None and Path(c).exists()

    def test_tts_models_base_from_env(self):
        from zapista.tts.voices import tts_models_base

        with patch.dict(os.environ, {"TTS_MODELS_BASE": "/custom/piper"}, clear=False):
            assert tts_models_base() == "/custom/piper"


# =============================================================================
# TTS — config
# =============================================================================


class TestTTSConfig:
    def test_tts_disabled_by_default(self):
        from zapista.tts.config import tts_enabled

        with patch.dict(os.environ, {"TTS_ENABLED": ""}, clear=False):
            assert tts_enabled() is False

    def test_tts_enabled_when_set(self):
        from zapista.tts.config import tts_enabled

        for val in ("1", "true", "yes", "TRUE"):
            with patch.dict(os.environ, {"TTS_ENABLED": val}, clear=False):
                assert tts_enabled() is True

    def test_tts_max_words_default(self):
        from zapista.tts.config import tts_max_words

        with patch.dict(os.environ, {"TTS_MAX_WORDS": ""}, clear=False):
            assert tts_max_words() == 40

    def test_tts_max_audio_seconds_default(self):
        from zapista.tts.config import tts_max_audio_seconds

        with patch.dict(os.environ, {"TTS_MAX_AUDIO_SECONDS": ""}, clear=False):
            assert tts_max_audio_seconds() == 15.0


# =============================================================================
# TTS — service (Piper mocked)
# =============================================================================


class TestTTSService:
    def test_synthesize_disabled_returns_none(self):
        from zapista.tts.service import synthesize_voice_note

        with patch("zapista.tts.service.tts_enabled", return_value=False):
            assert synthesize_voice_note("olá", "test") is None

    def test_synthesize_empty_text_returns_none(self):
        from zapista.tts.service import synthesize_voice_note

        with patch("zapista.tts.service.tts_enabled", return_value=True):
            assert synthesize_voice_note("", "test") is None
            assert synthesize_voice_note("   ", "test") is None

    def test_synthesize_exceeds_max_words_returns_none(self):
        from zapista.tts.service import synthesize_voice_note

        long_text = " ".join(["palavra"] * 50)
        with patch("zapista.tts.service.tts_enabled", return_value=True):
            with patch("zapista.tts.service.tts_max_words", return_value=40):
                assert synthesize_voice_note(long_text, "test") is None

    def test_synthesize_no_voice_returns_none(self):
        from zapista.tts.service import synthesize_voice_note

        with patch("zapista.tts.service.tts_enabled", return_value=True):
            with patch("zapista.tts.service.get_voice_paths", return_value=(None, None)):
                assert synthesize_voice_note("olá", "test") is None

    def test_synthesize_piper_fails_returns_none(self):
        from zapista.tts.service import synthesize_voice_note

        with patch("zapista.tts.service.tts_enabled", return_value=True):
            with patch("zapista.tts.service.get_voice_paths", return_value=("/fake/model.onnx", "/fake/config.json")):
                with patch("zapista.tts.service.piper_synthesize", return_value=False):
                    assert synthesize_voice_note("olá", "test") is None

    def test_synthesize_success_returns_ogg_path(self):
        """Piper e wav_to_ogg OK → retorna path .ogg."""
        from zapista.tts.service import synthesize_voice_note

        tmp = tempfile.mkdtemp()
        fid = "abc123abc123"
        (Path(tmp) / f"{fid}.ogg").touch()
        try:
            with patch("zapista.tts.service.tts_enabled", return_value=True):
                with patch("zapista.tts.service.tts_tmp_dir", return_value=tmp):
                    with patch("zapista.tts.service.get_voice_paths", return_value=("/m/model.onnx", "/m/config.json")):
                        with patch("zapista.tts.service.piper_synthesize", return_value=True):
                            with patch("zapista.tts.service.wav_to_ogg_opus", return_value=True):
                                with patch("zapista.tts.service.uuid.uuid4") as mu:
                                    mu.return_value.hex = fid + "x" * 12
                                    res = synthesize_voice_note("olá", "test")
            assert res is not None
            assert res.suffix == ".ogg"
            assert "abc123abc123" in str(res)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# TTS — audio (ffmpeg mocked)
# =============================================================================


class TestTTSAudio:
    def test_ensure_tmp_dir_creates_path(self):
        from zapista.tts.audio import ensure_tmp_dir

        import shutil
        tmp = tempfile.mkdtemp()
        sub = f"{tmp}/tts/sub"
        try:
            path = ensure_tmp_dir(sub)
            assert path.exists()
            assert path.is_dir()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cleanup_wav_removes_file(self):
        from zapista.tts.audio import cleanup_wav

        fd, p = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        path = Path(p)
        assert path.exists()
        cleanup_wav(path)
        assert not path.exists()

    def test_wav_to_ogg_audio_too_long_returns_false(self):
        from zapista.tts.audio import wav_to_ogg_opus

        with patch("zapista.tts.audio.get_duration_seconds", return_value=20.0):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(b"fake")
                wav = Path(f.name)
            try:
                ogg = wav.with_suffix(".ogg")
                assert wav_to_ogg_opus(wav, ogg, max_seconds=15.0) is False
            finally:
                wav.unlink(missing_ok=True)


# =============================================================================
# STT — transcribe (providers mocked)
# =============================================================================


class TestSTTTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_disabled_returns_empty(self):
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=False):
            result = await transcribe("dGVzdA==")
        assert result == ""

    @pytest.mark.asyncio
    async def test_transcribe_empty_base64_returns_empty(self):
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=True):
            result = await transcribe("")
            assert result == ""
            result = await transcribe("   ")
            assert result == ""

    @pytest.mark.asyncio
    async def test_transcribe_local_success(self):
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=True):
            with patch("zapista.stt.transcriber.stt_local_url", return_value="http://localhost:8080"):
                with patch("zapista.stt.transcriber.transcribe_local", new_callable=AsyncMock, return_value="remind me"):
                    result = await transcribe("dGVzdA==")
        assert result == "remind me"

    @pytest.mark.asyncio
    async def test_transcribe_local_fails_fallback_openai(self):
        """Whisper local falha → fallback OpenAI (OPENAI_API_KEY do install)."""
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=True):
            with patch("zapista.stt.transcriber.stt_local_url", return_value="http://localhost:8080"):
                with patch("zapista.stt.transcriber.transcribe_local", new_callable=AsyncMock, return_value=""):
                    with patch("zapista.stt.transcriber.openai_api_key", return_value="fake"):
                        with patch("zapista.stt.transcriber.transcribe_openai", new_callable=AsyncMock, return_value="openai text"):
                            result = await transcribe("dGVzdA==")
        assert result == "openai text"

    @pytest.mark.asyncio
    async def test_transcribe_all_fail_returns_empty(self):
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=True):
            with patch("zapista.stt.transcriber.stt_local_url", return_value="http://x"):
                with patch("zapista.stt.transcriber.transcribe_local", new_callable=AsyncMock, return_value=""):
                    with patch("zapista.stt.transcriber.openai_api_key", return_value=None):
                        result = await transcribe("dGVzdA==")
        assert result == ""


# =============================================================================
# STT — audio_utils
# =============================================================================


class TestSTTAudioUtils:
    def test_decode_base64_valid(self):
        from zapista.stt.audio_utils import decode_base64_to_temp

        path = decode_base64_to_temp(base64.b64encode(b"hello").decode())
        assert path is not None
        if path:
            try:
                assert path.read_bytes() == b"hello"
            finally:
                path.unlink(missing_ok=True)

    def test_decode_base64_invalid_returns_none(self):
        from zapista.stt.audio_utils import decode_base64_to_temp

        assert decode_base64_to_temp("!!!invalid!!!") is None

    def test_get_duration_seconds_missing_file(self):
        from zapista.stt.audio_utils import get_duration_seconds

        assert get_duration_seconds(Path("/nonexistent/file.wav")) is None

    def test_check_audio_duration_invalid_base64(self):
        from zapista.stt.audio_utils import check_audio_duration

        assert check_audio_duration("!!!") is None


# =============================================================================
# Stress: múltiplas chamadas rápidas
# =============================================================================


class TestTTSStressConcurrent:
    """Stress: muitas chamadas em sequência."""

    def test_resolve_locale_100_times(self):
        from zapista.tts.voices import resolve_locale_for_audio

        for _ in range(100):
            assert resolve_locale_for_audio("351912345678@s.whatsapp.net", "ptpt") == "pt-PT"
            assert resolve_locale_for_audio("5511999999999@s.whatsapp.net", "ptbr") == "pt-BR"
            assert resolve_locale_for_audio("x", "es") == "es"
            assert resolve_locale_for_audio("x", "en") == "en"

    def test_get_voice_paths_100_times_empty_base(self):
        from zapista.tts.voices import get_voice_paths

        base = tempfile.mkdtemp()
        with patch.dict(os.environ, {"TTS_MODELS_BASE": base}, clear=False):
            for _ in range(100):
                m, c = get_voice_paths("pt-BR")
                assert m is None or not Path(m).exists()
                assert c is None or not Path(c).exists()


class TestSTTStressConcurrent:
    @pytest.mark.asyncio
    async def test_transcribe_disabled_100_times(self):
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=False):
            for _ in range(100):
                assert await transcribe("dGVzdA==") == ""

    @pytest.mark.asyncio
    async def test_transcribe_mocked_50_times(self):
        from zapista.stt.transcriber import transcribe

        with patch("zapista.stt.transcriber.stt_enabled", return_value=True):
            with patch("zapista.stt.transcriber.stt_local_url", return_value="http://x"):
                with patch("zapista.stt.transcriber.transcribe_local", new_callable=AsyncMock, return_value="ok"):
                    for i in range(50):
                        result = await transcribe("dGVzdA==")
                        assert result == "ok"
