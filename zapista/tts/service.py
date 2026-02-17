"""
Serviço TTS: synthesize_voice_note(reply_text, chat_id, locale?) -> ogg_path | None.

Regras:
- Se > TTS_MAX_WORDS: retorna None (cair para texto)
- Piper gera WAV; se duração > 15s: retorna None
- WAV → OGG Opus
- locale: pt-BR, pt-PT, es, en (default do número ou override)

Para respostas longas (ex.: lista de lembretes) com pedido de áudio: split_text_for_tts
divide o texto em blocos <= max_words e o canal pode enviar vários voice notes.
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


def split_text_for_tts(text: str, max_words: int | None = None) -> list[str]:
    """
    Divide texto em blocos com <= max_words para enviar como vários áudios.
    Prioridade: parágrafos (\\n\\n), depois linhas (\\n), depois frases.
    """
    if max_words is None:
        max_words = tts_max_words()
    text = (text or "").strip()
    if not text or max_words <= 0:
        return []
    words = text.split()
    if len(words) <= max_words:
        return [text]

    chunks: list[str] = []
    # Tentar dividir por parágrafos
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) > 1:
        current: list[str] = []
        current_len = 0
        for p in paras:
            w = len(p.split())
            if current_len + w <= max_words:
                current.append(p)
                current_len += w
            else:
                if current:
                    chunks.append("\n\n".join(current))
                if w <= max_words:
                    current = [p]
                    current_len = w
                else:
                    # Parágrafo longo: dividir por linhas
                    for line in p.split("\n"):
                        lw = len(line.split())
                        if current_len + lw <= max_words:
                            current.append(line)
                            current_len += lw
                        else:
                            if current:
                                chunks.append("\n".join(current))
                            current = [line] if lw <= max_words else _split_by_words(line, max_words)
                            current_len = sum(len(s.split()) for s in current)
                    current_len = sum(len(s.split()) for s in current)
                current = []
        if current:
            chunks.append("\n\n".join(current))
        return chunks if chunks else [text]

    # Um único parágrafo: dividir por linhas
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) > 1:
        current = []
        current_len = 0
        for line in lines:
            w = len(line.split())
            if current_len + w <= max_words:
                current.append(line)
                current_len += w
            else:
                if current:
                    chunks.append("\n".join(current))
                if w <= max_words:
                    current = [line]
                    current_len = w
                else:
                    chunks.extend(_split_by_words(line, max_words))
                    current = []
                    current_len = 0
        if current:
            chunks.append("\n".join(current))
        return chunks if chunks else [text]

    return _split_by_words(text, max_words)


def _split_by_words(text: str, max_words: int) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def synthesize_voice_note(
    reply_text: str,
    chat_id: str,
    locale_override: str | None = None,
    phone_for_locale: str | None = None,
) -> Path | None:
    """
    Sintetiza texto em voice note (OGG Opus).
    locale_override: pedido explícito de idioma (None = usar default do utilizador).
    phone_for_locale: quando chat_id é LID, número para inferir idioma (ex.: 351910070509 → pt-PT).
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

    locale = resolve_locale_for_audio(chat_id, locale_override, phone_for_locale)
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
