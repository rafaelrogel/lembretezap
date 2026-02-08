"""Event tool: add/list events (filme, livro, musica, evento)."""

from typing import Any

from nanobot.agent.tools.base import Tool
from backend.database import SessionLocal
from backend.user_store import get_or_create_user
from backend.models_db import Event, AuditLog


class EventTool(Tool):
    """Add or list events (filme, livro, musica, generic evento)."""

    def __init__(self):
        self._chat_id = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "event"

    @property
    def description(self) -> str:
        return "Add or list events. action: add (tipo=filme|livro|musica|evento, nome, ...), list (tipo optional)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list"], "description": "add | list"},
                "tipo": {"type": "string", "enum": ["filme", "livro", "musica", "evento"], "description": "Type"},
                "nome": {"type": "string", "description": "Name (e.g. film title)"},
                "payload": {"type": "object", "description": "Extra data (optional)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        tipo: str = "evento",
        nome: str = "",
        payload: dict | None = None,
        **kwargs: Any,
    ) -> str:
        if not self._chat_id:
            return "Error: no user context"
        db = SessionLocal()
        try:
            user = get_or_create_user(db, self._chat_id)
            if action == "add":
                return self._add(db, user.id, tipo, nome, payload or {})
            if action == "list":
                return self._list(db, user.id, tipo)
            return f"Unknown action: {action}"
        finally:
            db.close()

    def _add(self, db, user_id: int, tipo: str, nome: str, payload: dict) -> str:
        if not nome and not payload:
            return "Error: nome or payload required for add"
        data = {"nome": nome or "", **payload}
        ev = Event(user_id=user_id, tipo=tipo, payload=data, deleted=False)
        db.add(ev)
        db.add(AuditLog(user_id=user_id, action="event_add", resource=tipo))
        db.commit()
        return f"Anotado: {tipo} '{nome or str(payload)}' (id: {ev.id})"

    def _list(self, db, user_id: int, tipo: str) -> str:
        q = db.query(Event).filter(Event.user_id == user_id, Event.deleted == False)
        if tipo:
            q = q.filter(Event.tipo == tipo)
        events = q.order_by(Event.created_at.desc()).limit(50).all()
        if not events:
            return f"Nenhum {tipo or 'evento'}."
        lines = [f"{e.id}. [{e.tipo}] {e.payload.get('nome', e.payload)}" for e in events]
        return "\n".join(lines)
