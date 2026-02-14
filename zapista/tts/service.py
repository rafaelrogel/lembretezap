"""
Serviço TTS: synthesize_voice_note(reply_text, chat_id, locale?) -> ogg_path | None.

Regras:
- Se > TTS_MAX_WORDS: retorna None (cair para texto)
- Piper gera WAV; se duração > 15s: retorna None
- WAV → OGG Opus
- locale: pt-BR, pt-PT, es, en (default do número ou override)
"""

import uuid
from pathlib import Path

from loguru import logger

from zapista.tts.audio import ensure_tmp_dir, cleanup_wav, wav_to_ogg_opus
from zapista.tts.config import (
    tts_enabled,
    tts_max_audio_seconds,
    tts_max_words,
    tts_tmp_dir,
)
from zapista.tts.piper_tts import piper_synthesize
from zapista.tts.voices import get_voice_paths, resolve_locale_for_audio


def synthesize_voice_note(
    reply_text: str,
    chat_id: str,
    locale_override: str | None = None,
) -> Path | None:
    """
    Sintetiza texto em voice note (OGG Opus).
    locale_override: pedido explícito de idioma (None = usar default do utilizador).
    Retorna path do ficheiro .ogg ou None (fallback para texto).
    """
    if not tts_enabled():
        return None

    text = (reply_text or "").strip()
    if not text:
        return None

    words = len(text.split())
    if words > tts_max_words():
        logger.debug(f"TTS skip: {words} words > {tts_max_words()}")
        return None

    locale = resolve_locale_for_audio(chat_id, locale_override)
    model_path, config_path = get_voice_paths(locale)
    if not model_path or not config_path:
        logger.debug(f"TTS: no voice for locale {locale}")
        return None

    base_dir = ensure_tmp_dir(tts_tmp_dir())
    file_id = uuid.uuid4().hex[:12]
    wav_path = base_dir / f"{file_id}.wav"
    ogg_path = base_dir / f"{file_id}.ogg"

    if not piper_synthesize(text, wav_path, model_path, config_path):
        return None

    try:
        if not wav_to_ogg_opus(wav_path, ogg_path, tts_max_audio_seconds()):
            return None
        if ogg_path.exists():
            return ogg_path
    finally:
        cleanup_wav(wav_path)

    return None
