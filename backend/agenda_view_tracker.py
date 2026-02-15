"""Contagem de visualizações da agenda por (chat_id, data) para mostrar prompt na segunda vez."""

from __future__ import annotations

# (chat_id, date_iso) -> número de vezes que viu agenda/hoje neste dia (timezone do user)
_views: dict[tuple[str, str], int] = {}


def record_agenda_view(chat_id: str, date_iso: str) -> int:
    """Regista uma visualização da agenda (via /hoje ou /agenda) e devolve o total de hoje."""
    key = (chat_id, date_iso)
    _views[key] = _views.get(key, 0) + 1
    return _views[key]


def get_agenda_view_count(chat_id: str, date_iso: str) -> int:
    """Devolve quantas vezes o user já viu a agenda nesta data (sem incrementar)."""
    return _views.get((chat_id, date_iso), 0)
