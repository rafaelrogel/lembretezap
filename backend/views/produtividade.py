"""Visão: /produtividade — relatório de produtividade (tarefas, lembretes, eventos)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_produtividade(ctx: "HandlerContext", mode: str = "semana") -> str:
    """Relatório de produtividade: evolução semanal ou mensal."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
    from backend.models_db import ReminderHistory, AuditLog, Event
    from backend.locale import (
        VIEW_PRODUTIVIDADE_HEADER, VIEW_STATS_LAST_4_WEEKS, VIEW_LAST_3_MONTHS,
        VIEW_MONTH_NAMES, VIEW_ERROR,
    )

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            today = now.date()
            since_naive = (now - timedelta(days=93)).astimezone(timezone.utc).replace(tzinfo=None)

            def _to_local_date(dt):
                if not dt:
                    return None
                if dt.tzinfo:
                    return dt.astimezone(tz).date()
                return dt.replace(tzinfo=timezone.utc).astimezone(tz).date()

            feito_by_day: dict[str, int] = {}
            rem_by_day: dict[str, int] = {}
            ev_by_day: dict[str, int] = {}

            for a in db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.action == "list_feito",
                AuditLog.created_at >= since_naive,
            ).all():
                d = _to_local_date(a.created_at)
                if d:
                    feito_by_day[d.isoformat()] = feito_by_day.get(d.isoformat(), 0) + 1

            for r in db.query(ReminderHistory).filter(
                ReminderHistory.user_id == user.id,
                ReminderHistory.status == "sent",
                ReminderHistory.delivered_at.isnot(None),
                ReminderHistory.delivered_at >= since_naive,
            ).all():
                d = _to_local_date(r.delivered_at)
                if d:
                    rem_by_day[d.isoformat()] = rem_by_day.get(d.isoformat(), 0) + 1

            for ev in db.query(Event).filter(
                Event.user_id == user.id,
                Event.deleted == False,
                Event.created_at >= since_naive,
            ).all():
                d = _to_local_date(ev.created_at)
                if d:
                    ev_by_day[d.isoformat()] = ev_by_day.get(d.isoformat(), 0) + 1

            month_names = VIEW_MONTH_NAMES.get(lang, VIEW_MONTH_NAMES["en"])
            lines = [VIEW_PRODUTIVIDADE_HEADER.get(lang, VIEW_PRODUTIVIDADE_HEADER["en"])]
            import calendar
            if mode == "semana":
                lines.append(VIEW_STATS_LAST_4_WEEKS.get(lang, VIEW_STATS_LAST_4_WEEKS["en"]))
                for i in range(4):
                    start = today - timedelta(days=6 + i * 7)
                    end = today - timedelta(days=i * 7)
                    fd = sum(feito_by_day.get((start + timedelta(days=j)).isoformat(), 0) for j in range(7))
                    rd = sum(rem_by_day.get((start + timedelta(days=j)).isoformat(), 0) for j in range(7))
                    ed = sum(ev_by_day.get((start + timedelta(days=j)).isoformat(), 0) for j in range(7))
                    lines.append(f"• S{i + 1} ({start.strftime('%d/%m')}–{end.strftime('%d/%m')}): {fd} tarefas | {rd} lembretes | {ed} eventos")
            else:
                lines.append(VIEW_LAST_3_MONTHS.get(lang, VIEW_LAST_3_MONTHS["en"]))
                for i in range(3):
                    m = today.month - 1 - i
                    y = today.year
                    while m < 1:
                        m += 12
                        y -= 1
                    start = datetime(y, m, 1, tzinfo=tz).date()
                    _, last_dom = calendar.monthrange(y, m)
                    end = datetime(y, m, last_dom, tzinfo=tz).date()
                    fd = rd = ed = 0
                    d = start
                    while d <= end and d <= today:
                        fd += feito_by_day.get(d.isoformat(), 0)
                        rd += rem_by_day.get(d.isoformat(), 0)
                        ed += ev_by_day.get(d.isoformat(), 0)
                        d += timedelta(days=1)
                    lines.append(f"• {month_names[m - 1]} {y}: {fd} tarefas | {rd} lembretes | {ed} eventos")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)


async def handle_produtividade(ctx: "HandlerContext", content: str) -> str | None:
    """/produtividade ou /produtividade mes. Aceita NL: produtividade."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip().lower()
    if not t.startswith("/produtividade"):
        return None
    rest = t[14:].strip()
    mode = "semana"
    if rest == "mes" or rest == "mês":
        mode = "mes"
    return _visao_produtividade(ctx, mode)