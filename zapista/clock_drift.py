"""
Verificação de desvio do relógio do servidor (VPS/Docker) em relação a uma fonte externa.

Executa a cada 45 min; em caso de desvio > limiar, regista ERROR e aplica correção
automática em memória (offset). O cron e a criação de jobs usam get_effective_time()
para que lembretes disparem na hora certa mesmo com relógio do host errado.

Override manual: se o relógio do servidor estiver errado e a API externa falhar,
defina CLOCK_OFFSET_SECONDS no ambiente. Ex.: servidor 7.5h atrasado = 27000
(segundos a somar a time.time() para obter a hora real).
"""

import asyncio
import os
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

# Limite do offset automático (API): ±12h. Evita aplicar offset absurdo se a API externa vier errada.
# CLOCK_OFFSET_SECONDS (env) não é limitado (override manual confiável).
CLOCK_DRIFT_AUTO_OFFSET_CAP_S = 12 * 3600

# Fonte externa de tempo UTC (JSON API)
EXTERNAL_TIME_URL = "https://worldtimeapi.org/api/timezone/Etc/UTC"

# Fontes redundantes via HTTP Date Header (RFC 2822). 
# Google e Apple são altamente confiáveis e raramente bloqueadas.
FALLBACK_TIME_URLS = [
    "https://www.google.com",
    "https://www.apple.com",
    "https://1.1.1.1",
]

# Tag para grep / alerting
CLOCK_DRIFT_ALERT_TAG = "CLOCK_DRIFT_ALERT"
CLOCK_DRIFT_CORRECTED_TAG = "CLOCK_DRIFT_CORRECTED"

# Offset em segundos a somar a time.time() para obter "hora efectiva" (corrigida). Thread-local safe.
_clock_offset_s: float = 0.0
_lock = threading.Lock()
_env_offset_applied = False


def _apply_env_offset() -> None:
    """Aplica offset a partir de CLOCK_OFFSET_SECONDS (override manual quando o relógio do servidor está errado)."""
    global _clock_offset_s, _env_offset_applied
    if _env_offset_applied:
        return
    raw = os.environ.get("CLOCK_OFFSET_SECONDS", "").strip()
    if not raw:
        return
    try:
        offset = float(raw)
        with _lock:
            _clock_offset_s = offset
        _env_offset_applied = True
        logger.info(
            "Clock drift: offset aplicado a partir de CLOCK_OFFSET_SECONDS=%.1f (hora do servidor + %.1fs = hora efectiva)",
            offset,
            offset,
        )
    except ValueError:
        logger.warning("CLOCK_OFFSET_SECONDS inválido (deve ser número): %r", raw[:20])


def get_effective_time() -> float:
    """
    Retorna a hora UTC efectiva para agendamento (cron, criação de jobs).
    Se foi detectado desvio grande, inclui o offset da correção automática.
    CLOCK_OFFSET_SECONDS (env) é aplicado na primeira chamada do loop ou aqui.
    """
    _apply_env_offset()
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


def get_current_offset() -> float:
    """Retorna o offset atual (em segundos) que está sendo somado ao time.time()."""
    with _lock:
        return _clock_offset_s


def get_drift_status() -> dict:
    """Retorna status do relógio para diagnóstico."""
    offset = get_current_offset()
    server_ts = time.time()
    effective_ts = server_ts + offset
    return {
        "server_ts": server_ts,
        "effective_ts": effective_ts,
        "offset_seconds": offset,
        "is_corrected": abs(offset) > 0.1,
    }


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
    external_ts = None
    
    import httpx
    
    # Tentativa 1: WorldTimeAPI (JSON)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                raw = data.get("unixtime") or data.get("datetime")
                if raw is not None:
                    if isinstance(raw, (int, float)):
                        external_ts = float(raw)
                    elif isinstance(raw, str) and raw.endswith("Z"):
                        from datetime import datetime
                        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        external_ts = dt.timestamp()
    except Exception as e:
        logger.debug(f"Clock drift: WorldTimeAPI failed ({e}), trying fallbacks...")

    # Tentativa 2: Fallbacks via HTTP Date Header
    if external_ts is None:
        from email.utils import parsedate_to_datetime
        for fallback_url in FALLBACK_TIME_URLS:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # HEAD é mais leve e contém o Header Date
                    r = await client.head(fallback_url)
                    date_str = r.headers.get("Date")
                    if date_str:
                        dt = parsedate_to_datetime(date_str)
                        external_ts = dt.timestamp()
                        logger.info(f"Clock drift: time synced via {fallback_url} Date header")
                        break
            except Exception as e:
                logger.debug(f"Clock drift: fallback {fallback_url} failed ({e})")

    if external_ts is None:
        logger.warning("Clock drift check: could not fetch external time from any source")
        return (True, None)  # Não alertar por falha de rede/API


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
        # Correção automática: aplicar offset (limitado a ±12h). Não sobrescrever se o utilizador definiu CLOCK_OFFSET_SECONDS.
        if abs_drift >= CLOCK_DRIFT_AUTO_CORRECT_THRESHOLD_S and not _env_offset_applied:
            offset_s = external_ts - server_ts
            capped = max(-CLOCK_DRIFT_AUTO_OFFSET_CAP_S, min(CLOCK_DRIFT_AUTO_OFFSET_CAP_S, offset_s))
            if capped != offset_s:
                logger.warning(
                    "Clock drift: offset da API limitado a ±12h (calculado={:.0f}s, aplicado={:.0f}s)",
                    offset_s,
                    capped,
                )
            _apply_offset(capped)
            logger.warning(
                "{} | offset aplicado={:.1f}s | Correção automática: agendamentos usam hora externa até próximo check.",
                CLOCK_DRIFT_CORRECTED_TAG,
                capped,
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
    e depois a cada interval_s segundos. Se CLOCK_OFFSET_SECONDS estiver definido, aplica-o primeiro.
    """
    _apply_env_offset()
    # Verificação imediata ao arranque: evita mostrar hora errada (ex.: 14:51 em vez de 22:20) até 45 min
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
