"""TTS configuration from environment."""

import os


def tts_enabled() -> bool:
    """True se TTS estiver ativa."""
    return os.environ.get("TTS_ENABLED", "").lower() in ("1", "true", "yes")


def tts_max_audio_seconds() -> float:
    """Duração máxima do áudio em segundos (default 15)."""
    try:
        return float(os.environ.get("TTS_MAX_AUDIO_SECONDS", "15"))
    except ValueError:
        return 15.0


def tts_max_words() -> int:
    """Máximo de palavras antes de cair para texto (default 40)."""
    try:
        return int(os.environ.get("TTS_MAX_WORDS", "40"))
    except ValueError:
        return 40


def tts_tmp_dir() -> str:
    """Directório para ficheiros temporários (ex.: /root/.zapista/tmp/tts)."""
    base = os.environ.get("ZAPISTA_DATA", "") or os.path.expanduser("~/.zapista")
    return os.environ.get("TTS_TMP_DIR", "").strip() or os.path.join(base, "tmp", "tts")


def tts_piper_timeout_seconds() -> float:
    """Timeout do subprocess Piper em segundos."""
    try:
        return float(os.environ.get("TTS_PIPER_TIMEOUT_SECONDS", "8"))
    except ValueError:
        return 8.0


def piper_bin() -> str | None:
    """Path do binário Piper (ex.: /usr/local/bin/piper). None se não configurado."""
    path = (os.environ.get("PIPER_BIN", "") or "").strip()
    return path if path else None
