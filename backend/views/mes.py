"""Visão: /mes — calendário ASCII do mês com marcadores nos dias com atividade."""

import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_mes(ctx: "HandlerContext", year: int, month: int) -> str:
    """Calendário ASCII do mês com marcadores (*) nos dias com eventos/lembretes."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import Event

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)

            first_day = datetime(year, month, 1, tzinfo=tz)
            _, last_dom = calendar.monthrange(year, month)
            last_day = datetime(year, month, last_dom, 23, 59, 59, tzinfo=tz)
            start_ms = int(first_day.timestamp() * 1000)
            end_ms = int(last_day.timestamp() * 1000)

            days_with_activity: set[int] = set()
            if ctx.cron_service:
                for job in ctx.cron_service.list_jobs():
                    if getattr(job.payload, "to", None) != ctx.chat_id:
                        continue
                    nr = getattr(job.state, "next_run_at_ms", None)
                    if nr and start_ms <= nr <= end_ms:
                        dt = datetime.fromtimestamp(nr / 1000, tz=ZoneInfo("UTC")).astimezone(tz)
                        days_with_activity.add(dt.day)

            events = db.query(Event).filter(
                Event.user_id == user.id,
                Event.deleted == False,
                Event.data_at.isnot(None),
            ).all()
            for ev in events:
                if not ev.data_at:
                    continue
                ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
                try:
                    ev_local = ev_date.astimezone(tz)
                except Exception:
                    ev_local = ev_date
                if ev_local.year == year and ev_local.month == month:
                    days_with_activity.add(ev_local.day)

            cal = calendar.Calendar(firstweekday=6)
            month_name = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"][month - 1]
            lines = [f"       {month_name} {year}", "  D  S  T  Q  Q  S  S"]
            for week in cal.monthdayscalendar(year, month):
                row = []
                for d in week:
                    if d == 0:
                        row.append("  ")
                    else:
                        mark = "*" if d in days_with_activity else " "
                        row.append(f"{d:2}{mark}")
                lines.append(" ".join(row))
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar calendário: {e}"


async def handle_mes(ctx: "HandlerContext", content: str) -> str | None:
    """/mes ou /mes 3 ou /mes 2026-03: calendário do mês."""
    t = content.strip().lower()
    if not t.startswith("/mes"):
        return None
    rest = t[4:].strip()
    now = datetime.now()
    year, month = now.year, now.month
    if rest:
        import re
        m = re.match(r"^(\d{1,2})\s*$", rest)
        if m:
            month = min(12, max(1, int(m.group(1))))
        else:
            m = re.match(r"^(\d{4})-(\d{1,2})\s*$", rest)
            if m:
                year = int(m.group(1))
                month = min(12, max(1, int(m.group(2))))
    return _visao_mes(ctx, year, month)
