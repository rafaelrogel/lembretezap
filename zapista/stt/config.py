"""STT configuration from environment."""

import os


def stt_enabled() -> bool:
    """True se transcrição de áudio estiver ativa."""
    return os.environ.get("STT_ENABLED", "").lower() in ("1", "true", "yes")


def stt_local_url() -> str | None:
    """URL do whisper.cpp server (ex.: http://stt:8080)."""
    url = (os.environ.get("STT_LOCAL_URL") or "").strip()
    return url if url else None


def openai_api_key() -> str | None:
    """Chave OpenAI para fallback (whisper API)."""
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("ZAPISTA_PROVIDERS__OPENAI__API_KEY") or "").strip()
    return key if key else None


def groq_api_key() -> str | None:
    """Chave Groq para fallback (whisper via Groq)."""
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    return key if key else None
