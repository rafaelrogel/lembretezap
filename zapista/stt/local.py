"""Cliente HTTP para whisper.cpp server."""

import httpx
from loguru import logger

from zapista.stt.audio_utils import prepare_audio_for_whisper


async def transcribe_local(audio_base64: str, base_url: str) -> str:
    """
    Envia áudio ao whisper.cpp e devolve texto transcrito.
    base_url: ex. http://stt:8080 (sem /inference)
    """
    wav_path = prepare_audio_for_whisper(audio_base64)
    if not wav_path:
        return ""
    try:
        url = base_url.rstrip("/") + "/inference"
        with open(wav_path, "rb") as f:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    url,
                    files={"file": (wav_path.name, f, "audio/wav")},
                    data={"response_format": "json"},
                )
        if r.status_code != 200:
            logger.warning(f"whisper.cpp error {r.status_code}: {r.text[:200]}")
            return ""
        data = r.json()
        # whisper.cpp server json: {"text": "..."} or similar
        text = data.get("text") if isinstance(data, dict) else ""
        return (text or "").strip()
    except Exception as e:
        logger.warning(f"whisper.cpp request failed: {e}")
        return ""
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass
