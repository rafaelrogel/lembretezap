"""Handlers package: re-exports all public handler functions for backward compatibility.

Previous monolithic handlers.py (1292 lines) split into:
  - lembrete.py: reminder flows, /lembrete, /recorrente, recurring events
  - lists.py:    /list, /add, /feito, /remove, /pendente, ambiguous
  - events.py:   /hora, /data
  - utils.py:    shared helpers, /start, /help, /stop
"""

from backend.handlers.lembrete import (
    handle_pending_confirmation,
    handle_vague_time_reminder,
    handle_lembrete,
    handle_recorrente,
    handle_recurring_prompt,
    handle_recurring_event,
)

from backend.handlers.lists import (
    handle_list_or_events_ambiguous,
    handle_list,
    handle_add,
    handle_feito,
    handle_remove,
    handle_pendente,
)

from backend.handlers.events import (
    handle_hora_data,
)

from backend.handlers.utils import (
    handle_start,
    handle_help,
    handle_stop,
)

__all__ = [
    "handle_pending_confirmation",
    "handle_vague_time_reminder",
    "handle_lembrete",
    "handle_recorrente",
    "handle_recurring_prompt",
    "handle_recurring_event",
    "handle_list_or_events_ambiguous",
    "handle_list",
    "handle_add",
    "handle_feito",
    "handle_remove",
    "handle_pendente",
    "handle_hora_data",
    "handle_start",
    "handle_help",
    "handle_stop",
]
