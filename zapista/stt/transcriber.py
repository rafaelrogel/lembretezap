"""Orquestra transcrição: whisper local → Groq → OpenAI."""

from loguru import logger

from zapista.stt.config import groq_api_key, openai_api_key, stt_enabled, stt_local_url
from zapista.stt.groq_fallback import transcribe_groq
from zapista.stt.local import transcribe_local
from zapista.stt.openai_fallback import transcribe_openai


async def transcribe(audio_base64: str) -> str:
    """
    Transcreve áudio base64 (OGG/Opus PTT WhatsApp) em texto.
    Ordem: whisper.cpp local → Groq → OpenAI.
    """
    if not stt_enabled():
        return ""
    if not (audio_base64 or "").strip():
        return ""
    local_url = stt_local_url()
    if local_url:
        text = await transcribe_local(audio_base64, local_url)
        if text:
            return text
    if groq_api_key():
        text = await transcribe_groq(audio_base64)
        if text:
            return text
    if openai_api_key():
        text = await transcribe_openai(audio_base64)
        if text:
            return text
    logger.warning("No STT provider succeeded")
    return ""
