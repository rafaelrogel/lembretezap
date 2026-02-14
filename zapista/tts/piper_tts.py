"""Piper TTS: gera WAV a partir de texto (múltiplas vozes: pt_BR, pt_PT, es_ES, en_US)."""

import subprocess
from pathlib import Path

from loguru import logger

from zapista.tts.config import piper_bin, tts_piper_timeout_seconds


def piper_synthesize(
    text: str,
    output_wav: Path,
    model_path: str,
    config_path: str | None = None,
) -> bool:
    """
    Executa Piper para sintetizar texto em WAV.
    model_path e config_path vêm do mapa PIPER_VOICES (por locale).
    Retorna True se sucesso.
    """
    bin_path = piper_bin()
    if not bin_path or not model_path:
        logger.debug("Piper not configured (PIPER_BIN or model_path)")
        return False

    if not Path(bin_path).exists():
        logger.warning(f"Piper binary not found: {bin_path}")
        return False

    if not Path(model_path).exists():
        logger.warning(f"Piper model not found: {model_path}")
        return False

    cfg = config_path or str(model_path).replace(".onnx", ".onnx.json")
    if not Path(cfg).exists():
        logger.warning(f"Piper config not found: {cfg}")
        return False

    timeout = tts_piper_timeout_seconds()
    try:
        proc = subprocess.Popen(
            [
                bin_path,
                "--model", model_path,
                "--config_file", cfg,
                "--output_file", str(output_wav),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        _, stderr = proc.communicate(input=text.strip(), timeout=timeout)
        if proc.returncode != 0:
            logger.warning(f"Piper failed (code {proc.returncode}): {stderr[:200]}")
            return False
        return output_wav.exists()
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        logger.warning(f"Piper timeout after {timeout}s")
        return False
    except Exception as e:
        logger.warning(f"Piper synthesize failed: {e}")
        return False
