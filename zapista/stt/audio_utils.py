"""Audio utilities: base64 decoding, ffmpeg conversion, duration validation."""

import base64
import os
import subprocess
import tempfile
from pathlib import Path

from loguru import logger

# Duração máxima em segundos — comandos de voz devem ser sucintos
MAX_DURATION_SEC = 60


def decode_base64_to_temp(
    b64: str, suffix: str = ".ogg"
) -> Path | None:
    """Decodifica base64 e grava num ficheiro temporário. Retorna o path ou None."""
    try:
        data = base64.b64decode(b64, validate=True)
    except Exception as e:
        logger.warning(f"Invalid base64 audio: {e}")
        return None
    if not data:
        return None
    try:
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return Path(path)
    except Exception as e:
        logger.warning(f"Failed to write temp audio: {e}")
        return None


def get_duration_seconds(path: Path) -> float | None:
    """Obtém duração do áudio com ffprobe. Retorna None se falhar."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.debug(f"ffprobe failed: {e}")
    return None


def convert_to_wav_mono_16k(path: Path, out_path: Path) -> bool:
    """Converte áudio para WAV mono 16kHz (whisper.cpp espera este formato sem --convert)."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(path),
                "-ac", "1", "-ar", "16000",
                "-acodec", "pcm_s16le",
                str(out_path),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return out_path.exists()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"ffmpeg convert failed: {e}")
        return False


def check_audio_duration(audio_base64: str) -> str | None:
    """
    Valida duração do áudio. Retorna None se OK, ou chave de erro ("AUDIO_TOO_LONG")
    para o gateway mapear ao idioma do utilizador.
    """
    inp = decode_base64_to_temp(audio_base64)
    if not inp:
        return None  # erro técnico; gateway usa mensagem genérica
    try:
        dur = get_duration_seconds(inp)
        if dur is not None and dur > MAX_DURATION_SEC:
            return "AUDIO_TOO_LONG"
        return None
    finally:
        try:
            inp.unlink(missing_ok=True)
        except OSError:
            pass


def prepare_audio_for_whisper(audio_base64: str) -> Path | None:
    """
    Base64 -> temp OGG -> (opcional) valida duração -> converte para WAV mono 16kHz.
    Retorna path do WAV ou None.
    """
    inp = decode_base64_to_temp(audio_base64)
    if not inp:
        return None
    try:
        dur = get_duration_seconds(inp)
        if dur is not None and dur > MAX_DURATION_SEC:
            logger.warning(f"Audio too long: {dur:.0f}s > {MAX_DURATION_SEC}s")
            return None
        out = inp.with_suffix(".wav")
        if convert_to_wav_mono_16k(inp, out):
            return out
        return None
    finally:
        try:
            inp.unlink(missing_ok=True)
        except OSError:
            pass
