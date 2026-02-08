"""Structured logging: trace_id correlation and optional JSON output.

Set NANOBOT_LOG_JSON=1 for JSON logs (e.g. in production). trace_id is set from
InboundMessage so all logs for a request can be correlated.
"""

import contextvars
import json
import os
import sys

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
    Configure loguru: add trace_id to format, optionally JSON sink.
    Call once at startup (e.g. in gateway). json_logs from NANOBOT_LOG_JSON env if None.
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
