"""Limites por dia: 80 eventos de agenda, 80 lembretes, 160 no total. Aviso aos 70%."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

LIMIT_EVENTS_PER_DAY = 80
LIMIT_REMINDERS_PER_DAY = 80
LIMIT_TOTAL_PER_DAY = 160
WARN_THRESHOLD = 0.7  # 70%

WARN_EVENTS = int(LIMIT_EVENTS_PER_DAY * WARN_THRESHOLD)      # 28
WARN_REMINDERS = int(LIMIT_REMINDERS_PER_DAY * WARN_THRESHOLD)  # 28
WARN_TOTAL = int(LIMIT_TOTAL_PER_DAY * WARN_THRESHOLD)        # 56


def count_events_on_date(db, user_id: int, target_date: date, tz_iana: str = "UTC") -> int:
    """Conta eventos (agenda) do user com data_at nessa data (no fuso do user)."""
    from backend.models_db import Event

    try:
        z = ZoneInfo(tz_iana)
    except Exception:
        z = ZoneInfo("UTC")
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=z)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=z)
    start_utc = start.astimezone(ZoneInfo("UTC"))
    end_utc = end.astimezone(ZoneInfo("UTC"))

    events = (
        db.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.deleted == False,
            Event.data_at.isnot(None),
            Event.data_at >= start_utc,
            Event.data_at <= end_utc,
        )
        .count()
    )
    return events


def count_reminders_on_date(cron_service, chat_id: str, target_date: date, tz_iana: str = "UTC") -> int:
    """Conta lembretes (jobs cron) do chat_id cujo next_run cai nessa data (no fuso do user).
    Ignora sub-jobs internos (avisos prévios, prazos) para não estourar o limite prematuramente.
    """
    try:
        z = ZoneInfo(tz_iana)
    except Exception:
        z = ZoneInfo("UTC")
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=z)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=z)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    jobs = cron_service.list_jobs(include_disabled=True) if hasattr(cron_service, "list_jobs") else []
    count = 0
    for j in jobs:
        # Pular se não for deste utilizador ou estiver desativado
        if getattr(j.payload, "to", None) != chat_id:
            continue
        if not getattr(j, "enabled", True):
            continue
        
        # Pular sub-jobs e automatismos (não contam para o limite de 40 lembretes do user)
        if getattr(j.payload, "parent_job_id", None):
            continue
        if getattr(j.payload, "deadline_check_for_job_id", None):
            continue
        if getattr(j.payload, "deadline_main_job_id", None):
            continue
        if getattr(j.payload, "is_proactive_nudge", False):
            continue
        if getattr(j.payload, "pomodoro_cycle", None) is not None:
            continue
        if getattr(j.payload, "pomodoro_phase", None) is not None:
            continue

        nr = getattr(j.state, "next_run_at_ms", None)
        if nr is not None and start_ms <= nr <= end_ms:
            count += 1
    return count


def check_event_limits(
    db, user_id: int, target_date: date, tz_iana: str,
    cron_service=None, chat_id: str | None = None,
) -> tuple[bool, bool, int, int, int]:
    """
    Verifica limites ao adicionar um evento nessa data.
    Retorna (allowed, at_warning, events_count, reminders_count, total_count).
    allowed=False se já atingiu o limite de eventos ou total.
    at_warning=True se após adicionar ficará >= 70% (para mostrar aviso).
    """
    events = count_events_on_date(db, user_id, target_date, tz_iana)
    reminders = 0
    if cron_service and chat_id:
        reminders = count_reminders_on_date(cron_service, chat_id, target_date, tz_iana)
    total = events + reminders

    # Limite de eventos por dia
    if events >= LIMIT_EVENTS_PER_DAY:
        return (False, False, events, reminders, total)
    # Limite total (eventos + lembretes) no dia
    if total >= LIMIT_TOTAL_PER_DAY:
        return (False, False, events, reminders, total)

    # Após adicionar 1 evento: events+1, total+1
    at_warning = (events + 1 >= WARN_EVENTS) or (total + 1 >= WARN_TOTAL)
    return (True, at_warning, events, reminders, total)


def check_reminder_limits(
    cron_service, chat_id: str, target_date: date, tz_iana: str,
    db=None, user_id: int | None = None,
) -> tuple[bool, bool, int, int, int]:
    """
    Verifica limites ao adicionar um lembrete nessa data.
    Retorna (allowed, at_warning, events_count, reminders_count, total_count).
    """
    reminders = count_reminders_on_date(cron_service, chat_id, target_date, tz_iana)
    events = 0
    if db is not None and user_id is not None:
        events = count_events_on_date(db, user_id, target_date, tz_iana)
    total = events + reminders

    if reminders >= LIMIT_REMINDERS_PER_DAY:
        return (False, False, events, reminders, total)
    if total >= LIMIT_TOTAL_PER_DAY:
        return (False, False, events, reminders, total)

    at_warning = (reminders + 1 >= WARN_REMINDERS) or (total + 1 >= WARN_TOTAL)
    return (True, at_warning, events, reminders, total)
