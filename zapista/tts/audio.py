"""Conversão WAV→OGG, medição de duração, limpeza."""

import os
import subprocess
from pathlib import Path

from loguru import logger

from zapista.stt.audio_utils import get_duration_seconds


def wav_to_ogg_opus(wav_path: Path, ogg_path: Path, max_seconds: float = 15.0) -> bool:
    """
    Converte WAV para OGG Opus (24k, 48kHz mono).
    Se duração > max_seconds, retorna False sem converter.
    """
    dur = get_duration_seconds(wav_path)
    if dur is not None and dur > max_seconds:
        logger.warning(f"TTS audio too long: {dur:.1f}s > {max_seconds}s")
        return False

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(wav_path),
                "-c:a", "libopus", "-b:a", "24k", "-ar", "48000", "-ac", "1",
                str(ogg_path),
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return ogg_path.exists()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"ffmpeg wav->ogg failed: {e}")
        return False


def cleanup_wav(wav_path: Path) -> None:
    """Remove ficheiro WAV após conversão."""
    try:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)
    except OSError as e:
        logger.debug(f"Cleanup wav failed: {e}")


def ensure_tmp_dir(tmp_dir: str) -> Path:
    """Garante que o diretório existe."""
    path = Path(tmp_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
