"""Structured logging: trace_id correlation, optional JSON output, file rotation.

- NANOBOT_LOG_JSON=1 — JSON logs (stderr)
- NANOBOT_LOG_FILE=/path/to/logs — escreve em ficheiro com rotação (10 MB, 7 dias)
- Docker: usar logging options no docker-compose para rotação dos logs do container
"""

import contextvars
import json
import os
import sys
from pathlib import Path

# Context var for request trace_id (set at message entry)
_trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Current request trace_id for correlation."""
    return _trace_id_ctx.get() or "-"


def set_trace_id(trace_id: str | None) -> contextvars.Token[str]:
    """Set trace_id for the current context. Return token for reset."""
    return _trace_id_ctx.set(trace_id or "")


def reset_trace_id(token: contextvars.Token[str]) -> None:
    """Restore previous trace_id (e.g. after request done)."""
    _trace_id_ctx.reset(token)


def _sink_json(record: dict) -> None:
    """Loguru sink: write one JSON object per line."""
    payload = {
        "ts": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "msg": record["message"],
        "trace_id": _trace_id_ctx.get() or "-",
    }
    for k, v in record["extra"].items():
        if v is not None and v != "":
            payload[k] = v
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


def _trace_id_filter(record: dict) -> bool:
    """Inject current trace_id into every log record."""
    record["extra"].setdefault("trace_id", _trace_id_ctx.get() or "-")
    return True


def configure_logging(json_logs: bool | None = None) -> None:
    """
    Configure loguru: add trace_id to format, optionally JSON sink, optional file with rotation.
    Call once at startup (e.g. in gateway). json_logs from NANOBOT_LOG_JSON env if None.

    NANOBOT_LOG_FILE: se definido, escreve também em ficheiro com rotação (10 MB, 7 dias).
    """
    from loguru import logger

    if json_logs is None:
        json_logs = os.environ.get("NANOBOT_LOG_JSON", "").strip() in ("1", "true", "yes")

    level = os.environ.get("NANOBOT_LOG_LEVEL", "INFO")
    logger.remove()

    if json_logs:
        logger.add(_sink_json, format="{message}", level=level, filter=_trace_id_filter)
    else:
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[trace_id]}</cyan> | {name}:{function}:{line} - <level>{message}</level>\n",
            level=level,
            filter=_trace_id_filter,
        )

    log_file = os.environ.get("NANOBOT_LOG_FILE", "").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(path),
            rotation="10 MB",
            retention="7 days",
            compression="gz",
            level=level,
            filter=_trace_id_filter,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[trace_id]} | {name}:{function}:{line} - {message}\n",
        )
