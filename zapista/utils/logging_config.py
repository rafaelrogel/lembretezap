"""Structured logging: trace_id correlation, optional JSON output, file rotation.

- ZAPISTA_LOG_JSON=1 — JSON logs (stderr)
- ZAPISTA_LOG_FILE=/path/to/logs — escreve em ficheiro com rotação (10 MB, 7 dias)
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


def configure_logging(json_logs: bool | None = None) -> None:
    """
    No longer configures loguru. zapista now uses backend.logger.
    This function is kept for backward compatibility (e.g. gateway calls it).
    """
    pass
