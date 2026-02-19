"""Event tool: add/list events (filme, livro, musica, evento)."""

from typing import Any

from zapista.agent.tools.base import Tool
from backend.database import SessionLocal
from backend.user_store import get_or_create_user, get_user_language
from backend.models_db import Event, AuditLog
from backend.sanitize import sanitize_string, sanitize_payload, MAX_EVENT_NAME_LEN


class EventTool(Tool):
    """Add or list events (filme, livro, musica, generic evento)."""

    def __init__(self):
        self._chat_id = ""

    def _get_lang(self) -> str:
        try:
            db = SessionLocal()
            try:
                return get_user_language(db, self._chat_id) or "pt-BR"
            finally:
                db.close()
        except Exception:
            return "pt-BR"

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
        data: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self._chat_id:
            return "Error: no user context"
        db = SessionLocal()
        try:
            user = get_or_create_user(db, self._chat_id)
            if action == "add":
                return self._add(db, user.id, tipo, nome, payload or {}, data_str=data)
            if action == "list":
                return self._list(db, user.id, tipo)
            if action == "remove":
                return self._remove(db, user.id, nome or "")
            return f"Unknown action: {action}"
        finally:
            db.close()

    def _add(self, db, user_id: int, tipo: str, nome: str, payload: dict, data_str: str | None = None) -> str:
        from backend.guardrails import is_absurd_request
        from dateutil.parser import parse as parse_dt
        from backend.user_store import get_user_timezone
        from zoneinfo import ZoneInfo
        
        absurd = is_absurd_request(nome or "")
        if absurd:
            return absurd
        nome = sanitize_string(nome or "", MAX_EVENT_NAME_LEN)
        payload = sanitize_payload(payload) if payload else {}
        if not nome and not payload:
            return "Error: nome or payload required for add"
        
        tipo = tipo if tipo in ("filme", "livro", "musica", "evento") else "evento"
        
        # Enforce date for "evento" (agenda)
        valid_date = None
        if data_str:
            try:
                # Tenta parsear data fornecida
                # Se for só hora, usa hoje. Se for data, usa 00:00. 
                # Ideal é que o LLM já mande ISO ou algo parseável.
                valid_date = parse_dt(data_str, fuzzy=True)
            except Exception:
                pass
        
        # Se for evento genérico e não tiver data, rejeita.
        if tipo == "evento" and not valid_date:
            from backend.locale import EVENT_REQUIRES_DATE
            _lang = self._get_lang()
            return EVENT_REQUIRES_DATE.get(_lang, EVENT_REQUIRES_DATE["en"])

        data = {"nome": nome, **payload}
        ev = Event(
            user_id=user_id, 
            tipo=tipo, 
            payload=data, 
            data_at=valid_date,  # Persiste a data se houver
            deleted=False
        )
        db.add(ev)
        db.add(AuditLog(user_id=user_id, action="event_add", resource=tipo))
        db.commit()
        
        from backend.locale import EVENT_ADDED, EVENT_CALENDAR_IMPORTED
        _lang = self._get_lang()
        date_msg = ""
        if ev.data_at:
            tz_iana = get_user_language(db, str(user_id)) or "UTC"
            date_msg = f" em {ev.data_at.strftime('%d/%m %H:%M')}"
        return EVENT_ADDED.get(_lang, EVENT_ADDED["en"]).format(
            tipo=tipo, name=nome or str(payload), date_msg=date_msg, id=ev.id
        )

    def _list(self, db, user_id: int, tipo: str) -> str:
        from zoneinfo import ZoneInfo
        from backend.user_store import get_user_timezone

        q = db.query(Event).filter(Event.user_id == user_id, Event.deleted == False)
        if tipo:
            q = q.filter(Event.tipo == tipo)
        events = q.order_by(Event.created_at.desc()).limit(50).all()
        from backend.locale import EVENT_NONE_FOUND, EVENT_CALENDAR_IMPORTED
        _lang = self._get_lang()
        if not events:
            return EVENT_NONE_FOUND.get(_lang, EVENT_NONE_FOUND["en"]).format(tipo=tipo or "evento")
        cal_imported = EVENT_CALENDAR_IMPORTED.get(_lang, EVENT_CALENDAR_IMPORTED["en"])
        tz_iana = get_user_timezone(db, self._chat_id) or "UTC"
        try:
            tz = ZoneInfo(tz_iana)
        except Exception:
            tz = ZoneInfo("UTC")
        lines = []
        for e in events:
            pl = e.payload or {}
            nome = pl.get("nome", pl)
            suf = cal_imported if pl.get("source") == "ics" else ""
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
        try:
            from zapista.clock_drift import get_effective_time
            _now_ts = get_effective_time()
        except Exception:
            import time
            _now_ts = time.time()
        today = datetime.fromtimestamp(_now_ts, tz=tz).date()
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
        from backend.locale import EVENT_REMOVE_NOT_FOUND, EVENT_REMOVE_MULTIPLE, EVENT_REMOVED
        _lang = self._get_lang()
        ref_lower = nome_ref.lower()
        matched = [e for e in today_events if ref_lower in (e.payload.get("nome", "") or "").lower()]
        if not matched:
            return EVENT_REMOVE_NOT_FOUND.get(_lang, EVENT_REMOVE_NOT_FOUND["en"]).format(name=nome_ref)
        if len(matched) > 1:
            names = ", ".join((e.payload.get("nome", "") or "?") for e in matched[:5])
            return EVENT_REMOVE_MULTIPLE.get(_lang, EVENT_REMOVE_MULTIPLE["en"]).format(names=names)
        ev = matched[0]
        ev.deleted = True
        db.add(AuditLog(user_id=user_id, action="event_remove", resource=ev.tipo))
        db.commit()
        nome = ev.payload.get("nome", "") or "evento"
        return EVENT_REMOVED.get(_lang, EVENT_REMOVED["en"]).format(name=nome)
