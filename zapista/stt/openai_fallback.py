"""Fallback de transcrição com OpenAI Whisper API."""

import base64
import tempfile
from pathlib import Path

import httpx
from loguru import logger

from zapista.stt.audio_utils import decode_base64_to_temp, get_duration_seconds
from zapista.stt.config import openai_api_key

MAX_DURATION_SEC = 60


async def transcribe_openai(audio_base64: str) -> str:
    """Transcreve áudio usando OpenAI Whisper API."""
    key = openai_api_key()
    if not key:
        logger.debug("OpenAI API key not set, skipping Whisper fallback")
        return ""
    inp = decode_base64_to_temp(audio_base64)
    if not inp:
        return ""
    try:
        dur = get_duration_seconds(inp)
        if dur is not None and dur > MAX_DURATION_SEC:
            logger.warning(f"Audio too long for OpenAI: {dur:.0f}s")
            return ""
        with open(inp, "rb") as f:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (inp.name, f, "audio/ogg")},
                    data={"model": "whisper-1"},
                )
        if r.status_code != 200:
            logger.warning(f"OpenAI Whisper error {r.status_code}: {r.text[:200]}")
            return ""
        data = r.json()
        text = data.get("text") if isinstance(data, dict) else ""
        return (text or "").strip()
    except Exception as e:
        logger.warning(f"OpenAI Whisper failed: {e}")
        return ""
    finally:
        try:
            inp.unlink(missing_ok=True)
        except OSError:
            pass
