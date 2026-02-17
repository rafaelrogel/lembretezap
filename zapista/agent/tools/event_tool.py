"""Event tool: add/list events (filme, livro, musica, evento)."""

from typing import Any

from zapista.agent.tools.base import Tool
from backend.database import SessionLocal
from backend.user_store import get_or_create_user
from backend.models_db import Event, AuditLog
from backend.sanitize import sanitize_string, sanitize_payload, MAX_EVENT_NAME_LEN


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
        return "Add, list or remove events. action: add (tipo=filme|livro|musica|evento, nome, ...), list (tipo optional), remove (nome=substring to match today's event to remove from agenda)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "remove"], "description": "add | list | remove"},
                "tipo": {"type": "string", "enum": ["filme", "livro", "musica", "evento"], "description": "Type"},
                "nome": {"type": "string", "description": "Name (e.g. film title); for remove, substring to match event name)"},
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
            if action == "remove":
                return self._remove(db, user.id, nome or "")
            return f"Unknown action: {action}"
        finally:
            db.close()

    def _add(self, db, user_id: int, tipo: str, nome: str, payload: dict) -> str:
        from backend.guardrails import is_absurd_request
        absurd = is_absurd_request(nome or "")
        if absurd:
            return absurd
        nome = sanitize_string(nome or "", MAX_EVENT_NAME_LEN)
        payload = sanitize_payload(payload) if payload else {}
        if not nome and not payload:
            return "Error: nome or payload required for add"
        tipo = tipo if tipo in ("filme", "livro", "musica", "evento") else "evento"
        data = {"nome": nome, **payload}
        ev = Event(user_id=user_id, tipo=tipo, payload=data, deleted=False)
        db.add(ev)
        db.add(AuditLog(user_id=user_id, action="event_add", resource=tipo))
        db.commit()
        return f"Anotado: {tipo} '{nome or str(payload)}' (id: {ev.id})"

    def _list(self, db, user_id: int, tipo: str) -> str:
        from zoneinfo import ZoneInfo
        from backend.user_store import get_user_timezone

        q = db.query(Event).filter(Event.user_id == user_id, Event.deleted == False)
        if tipo:
            q = q.filter(Event.tipo == tipo)
        events = q.order_by(Event.created_at.desc()).limit(50).all()
        if not events:
            return f"Nenhum {tipo or 'evento'}."
        tz_iana = get_user_timezone(db, self._chat_id) or "UTC"
        try:
            tz = ZoneInfo(tz_iana)
        except Exception:
            tz = ZoneInfo("UTC")
        lines = []
        for e in events:
            pl = e.payload or {}
            nome = pl.get("nome", pl)
            suf = " (importado do calendário)" if pl.get("source") == "ics" else ""
            time_suf = ""
            if e.data_at:
                dt = e.data_at if e.data_at.tzinfo else e.data_at.replace(tzinfo=ZoneInfo("UTC"))
                try:
                    local = dt.astimezone(tz)
                    time_suf = f" — {local.strftime('%H:%M %d/%m')}"
                except Exception:
                    time_suf = f" — {e.data_at.strftime('%H:%M %d/%m')}"
            lines.append(f"{e.id}. [{e.tipo}] {nome}{time_suf}{suf}")
        return "\n".join(lines)

    def _remove(self, db, user_id: int, nome_ref: str) -> str:
        """Remove da agenda (soft-delete) evento(s) de hoje cujo nome contém nome_ref."""
        from zoneinfo import ZoneInfo
        from datetime import datetime
        from backend.user_store import get_user_timezone

        nome_ref = (nome_ref or "").strip()
        if not nome_ref:
            return "Error: nome required for remove (e.g. substring of event name)"
        tz_iana = get_user_timezone(db, self._chat_id) or "UTC"
        try:
            tz = ZoneInfo(tz_iana)
        except Exception:
            tz = ZoneInfo("UTC")
        today = datetime.now(tz).date()
        events = (
            db.query(Event)
            .filter(
                Event.user_id == user_id,
                Event.deleted == False,
                Event.data_at.isnot(None),
            )
            .all()
        )
        today_events = []
        for ev in events:
            if not ev.data_at:
                continue
            ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
            try:
                ev_local = ev_date.astimezone(tz).date()
            except Exception:
                ev_local = ev_date.date()
            if ev_local == today:
                today_events.append(ev)
        ref_lower = nome_ref.lower()
        matched = [e for e in today_events if ref_lower in (e.payload.get("nome", "") or "").lower()]
        if not matched:
            return f"Nenhum evento de hoje com \"{nome_ref}\" na agenda."
        if len(matched) > 1:
            names = ", ".join((e.payload.get("nome", "") or "?") for e in matched[:5])
            return f"Vários eventos coincidem. Especifica: {names}"
        ev = matched[0]
        ev.deleted = True
        db.add(AuditLog(user_id=user_id, action="event_remove", resource=ev.tipo))
        db.commit()
        nome = ev.payload.get("nome", "") or "evento"
        return f"Removido da agenda: \"{nome}\"."
