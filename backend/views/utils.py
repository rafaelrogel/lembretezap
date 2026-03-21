"""Utilitários comuns para visões de agenda e lembretes."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

def get_events_in_period(db, user_id: int, start_date, end_date, tz, lang: str = "pt-BR") -> list:
    """Eventos (agenda) do user no intervalo [start_date, end_date]."""
    from backend.models_db import Event
    
    local_start = datetime.combine(start_date, time.min).replace(tzinfo=tz)
    local_end = datetime.combine(end_date, time.max).replace(tzinfo=tz)
    
    start_dt = local_start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_dt = local_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    events = db.query(Event).filter(
        Event.user_id == user_id,
        Event.tipo == "evento",
        Event.deleted == False,
        Event.data_at.between(start_dt, end_dt)
    ).all()
    
    out = []
    seen = set()
    for ev in events:
        from backend.locale import EVENT_UNKNOWN
        nome = ev.payload.get("nome", EVENT_UNKNOWN.get(lang, "Evento Desconhecido")).strip()
        if not ev.data_at:
            continue
            
        ev_date = ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
        try:
            ev_local = ev_date.astimezone(tz).date()
        except Exception:
            ev_local = ev_date.date()
            
        key = (ev_local, nome.lower())
        if key in seen:
            continue
        seen.add(key)
        
        out.append((ev_local, ev.data_at, nome))
        
    out.sort(key=lambda x: (x[0], x[1] or datetime.min))
    return out

def get_reminders_in_period(ctx: "HandlerContext", tz, start_utc_ms: int, end_utc_ms: int) -> list:
    """Lembretes (cron) do chat no intervalo [start_utc_ms, end_utc_ms]."""
    reminders = []
    if ctx.cron_service:
        for job in ctx.cron_service.list_jobs():
            if getattr(job.payload, "to", None) != ctx.chat_id:
                continue
            # Filtrar: avisos pré-evento, nudges proativos e deadline checkers
            if getattr(job.payload, "parent_job_id", None):
                continue
            if getattr(job.payload, "is_proactive_nudge", False):
                continue
            if getattr(job.payload, "deadline_check_for_job_id", None):
                continue
            if getattr(job.payload, "deadline_main_job_id", None):
                continue
            nr = getattr(job.state, "next_run_at_ms", None)
            if nr and start_utc_ms <= nr <= end_utc_ms:
                dt = datetime.fromtimestamp(nr / 1000, tz=ZoneInfo("UTC")).astimezone(tz)
                reminders.append((dt, getattr(job.payload, "message", "") or job.name))
    reminders.sort(key=lambda x: x[0])
    return reminders
