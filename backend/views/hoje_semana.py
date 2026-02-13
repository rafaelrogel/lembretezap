"""Visão: /hoje, /semana — lembretes e eventos no período."""

from datetime import timedelta
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_hoje_semana(ctx: "HandlerContext", dias: int) -> str:
    """dias=1 para hoje, dias=7 para semana."""
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
            from datetime import datetime
            now = datetime.now(tz)
            today = now.date()
            end_date = today + timedelta(days=dias - 1) if dias > 1 else today
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
            period_end = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=tz)
            today_start_utc_ms = int(today_start.timestamp() * 1000)
            period_end_utc_ms = int(period_end.timestamp() * 1000)

            lines = []
            if dias == 1:
                lines.append("📅 **Hoje**")
            else:
                lines.append(f"📅 **Próximos {dias} dias** (até {end_date.strftime('%d/%m')})")

            reminders = []
            if ctx.cron_service:
                for job in ctx.cron_service.list_jobs():
                    if getattr(job.payload, "to", None) != ctx.chat_id:
                        continue
                    nr = getattr(job.state, "next_run_at_ms", None)
                    if nr and today_start_utc_ms <= nr <= period_end_utc_ms:
                        dt = datetime.fromtimestamp(nr / 1000, tz=ZoneInfo("UTC")).astimezone(tz)
                        reminders.append((dt, getattr(job.payload, "message", "") or job.name))
            reminders.sort(key=lambda x: x[0])
            if reminders:
                for dt, msg in reminders[:15]:
                    lines.append(f"• {dt.strftime('%H:%M')} — {msg[:50]}{'…' if len(msg) > 50 else ''}")
            else:
                lines.append("• Nenhum lembrete agendado.")

            events = db.query(Event).filter(Event.user_id == user.id, Event.deleted == False, Event.data_at.isnot(None)).all()
            event_list = []
            for ev in events:
                if not ev.data_at:
                    continue
                ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
                try:
                    ev_local = ev_date.astimezone(tz).date()
                except Exception:
                    ev_local = ev_date.date()
                if today <= ev_local <= end_date:
                    nome = (ev.payload or {}).get("nome", "") if isinstance(ev.payload, dict) else str(ev.payload)[:40]
                    event_list.append((ev_local, ev.data_at, nome or "Evento"))
            event_list.sort(key=lambda x: (x[0], x[1] or datetime.min))
            if event_list:
                lines.append("")
                for d, _, nome in event_list[:15]:
                    lines.append(f"• {d.strftime('%d/%m')} — {nome[:50]}")
            else:
                if dias == 1:
                    lines.append("• Nenhum evento hoje.")

            return "\n".join(lines) if lines else "Nada para mostrar."
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar visão: {e}"


async def handle_hoje(ctx: "HandlerContext", content: str) -> str | None:
    """/hoje: visão rápida do dia."""
    if not content.strip().lower().startswith("/hoje"):
        return None
    return _visao_hoje_semana(ctx, 1)


async def handle_semana(ctx: "HandlerContext", content: str) -> str | None:
    """/semana: visão rápida da semana."""
    if not content.strip().lower().startswith("/semana"):
        return None
    return _visao_hoje_semana(ctx, 7)
