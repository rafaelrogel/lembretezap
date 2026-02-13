"""Fallback de transcrição com Groq Whisper API."""

from pathlib import Path

import httpx
from loguru import logger

from zapista.stt.audio_utils import decode_base64_to_temp, get_duration_seconds
from zapista.stt.config import groq_api_key

MAX_DURATION_SEC = 60


async def transcribe_groq(audio_base64: str) -> str:
    """Transcreve áudio usando Groq Whisper API (rápido, tier gratuito)."""
    key = groq_api_key()
    if not key:
        logger.debug("Groq API key not set, skipping Groq fallback")
        return ""
    inp = decode_base64_to_temp(audio_base64)
    if not inp:
        return ""
    try:
        dur = get_duration_seconds(inp)
        if dur is not None and dur > MAX_DURATION_SEC:
            logger.warning(f"Audio too long for Groq: {dur:.0f}s")
            return ""
        with open(inp, "rb") as f:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (inp.name, f, "audio/ogg")},
                    data={"model": "whisper-large-v3"},
                )
        if r.status_code != 200:
            logger.warning(f"Groq Whisper error {r.status_code}: {r.text[:200]}")
            return ""
        data = r.json()
        text = data.get("text") if isinstance(data, dict) else ""
        return (text or "").strip()
    except Exception as e:
        logger.warning(f"Groq Whisper failed: {e}")
        return ""
    finally:
        try:
            inp.unlink(missing_ok=True)
        except OSError:
            pass
