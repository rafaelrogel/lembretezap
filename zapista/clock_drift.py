"""
Verificação de desvio do relógio do servidor (VPS/Docker) em relação a uma fonte externa.

Executa a cada 45 min; em caso de desvio > limiar, regista ERROR e aplica correção
automática em memória (offset). O cron e a criação de jobs usam get_effective_time()
para que lembretes disparem na hora certa mesmo com relógio do host errado.
"""

import asyncio
import threading
import time
from typing import Tuple

from loguru import logger

# Intervalo entre verificações (45 min)
CLOCK_DRIFT_INTERVAL_S = 45 * 60

# Desvio que dispara alerta ERROR (segundos)
CLOCK_DRIFT_ALERT_THRESHOLD_S = 60

# Desvio a partir do qual aplicamos correção automática (segundos). Ex.: 60 = corrigir se > 1 min
CLOCK_DRIFT_AUTO_CORRECT_THRESHOLD_S = 60

# Fonte externa de tempo UTC (sem API key)
EXTERNAL_TIME_URL = "https://worldtimeapi.org/api/timezone/Etc/UTC"

# Tag para grep / alerting
CLOCK_DRIFT_ALERT_TAG = "CLOCK_DRIFT_ALERT"
CLOCK_DRIFT_CORRECTED_TAG = "CLOCK_DRIFT_CORRECTED"

# Offset em segundos a somar a time.time() para obter "hora efectiva" (corrigida). Thread-local safe.
_clock_offset_s: float = 0.0
_lock = threading.Lock()


def get_effective_time() -> float:
    """
    Retorna a hora UTC efectiva para agendamento (cron, criação de jobs).
    Se foi detectado desvio grande, inclui o offset da correção automática.
    """
    with _lock:
        return time.time() + _clock_offset_s


def get_effective_time_ms() -> int:
    """Hora efectiva em milissegundos (para at_ms, next_run_at_ms)."""
    return int(get_effective_time() * 1000)


def _apply_offset(offset_s: float) -> None:
    global _clock_offset_s
    with _lock:
        _clock_offset_s = offset_s


def _clear_offset_if_set() -> None:
    global _clock_offset_s
    with _lock:
        if _clock_offset_s != 0:
            _clock_offset_s = 0.0
            logger.info("Clock drift: offset removido (relógio dentro do limiar).")


async def check_clock_drift(
    *,
    threshold_s: float = CLOCK_DRIFT_ALERT_THRESHOLD_S,
    url: str = EXTERNAL_TIME_URL,
) -> Tuple[bool, float | None]:
    """
    Compara time.time() com a hora UTC de uma fonte externa.

    Returns:
        (ok, drift_seconds): ok=False se drift > threshold ou falha; drift_seconds é o desvio (positivo = servidor à frente).
    """
    server_ts = time.time()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning(f"Clock drift check: could not fetch external time: {e}")
        return (True, None)  # Não alertar por falha de rede

    raw = data.get("unixtime") or data.get("datetime")
    if raw is None:
        logger.warning("Clock drift check: no unixtime/datetime in response")
        return (True, None)

    if isinstance(raw, (int, float)):
        external_ts = float(raw)
    elif isinstance(raw, str) and raw.endswith("Z"):
        from datetime import datetime, timezone
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            external_ts = dt.timestamp()
        except Exception:
            logger.warning("Clock drift check: could not parse datetime")
            return (True, None)
    else:
        logger.warning("Clock drift check: unknown time format")
        return (True, None)

    drift_s = server_ts - external_ts
    abs_drift = abs(drift_s)

    if abs_drift > threshold_s:
        logger.error(
            "{} | drift_seconds={:.1f} server_ts={:.0f} external_ts={:.0f} | "
            "Relógio do servidor desalinhado: lembretes podem disparar na hora errada. "
            "Verifique NTP e TZ no VPS/Docker.",
            CLOCK_DRIFT_ALERT_TAG,
            drift_s,
            server_ts,
            external_ts,
        )
        # Correção automática: aplicar offset para que get_effective_time() = hora externa
        if abs_drift >= CLOCK_DRIFT_AUTO_CORRECT_THRESHOLD_S:
            _apply_offset(external_ts - server_ts)
            logger.warning(
                "{} | offset aplicado={:.1f}s | Correção automática: agendamentos usam hora externa até próximo check.",
                CLOCK_DRIFT_CORRECTED_TAG,
                external_ts - server_ts,
            )
        return (False, drift_s)

    # Desvio dentro do aceitável: remover offset (relógio pode ter sido corrigido por NTP)
    _clear_offset_if_set()
    logger.debug(
        "Clock drift check OK (drift_seconds={:.1f}, threshold={:.0f}s)",
        drift_s,
        threshold_s,
    )
    return (True, drift_s)


async def clock_drift_loop(
    *,
    interval_s: int = CLOCK_DRIFT_INTERVAL_S,
    threshold_s: float = CLOCK_DRIFT_ALERT_THRESHOLD_S,
) -> None:
    """
    Loop em background: executa check_clock_drift ao arranque (para corrigir hora logo)
    e depois a cada interval_s segundos.
    """
    # Verificação imediata ao arranque: evita mostrar hora errada (ex.: 14:51 em vez de 20:42) até 45 min
    try:
        await check_clock_drift(threshold_s=threshold_s)
    except Exception as e:
        logger.debug(f"Clock drift initial check: {e}")
    while True:
        await asyncio.sleep(interval_s)
        try:
            await check_clock_drift(threshold_s=threshold_s)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Clock drift loop error: {e}")
