"""Visão: /stats — estatísticas de tarefas feitas e lembretes."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_stats(ctx: "HandlerContext", mode: str = "resumo") -> str:
    """Estatísticas: tarefas feitas (list_feito) e lembretes recebidos (ReminderHistory sent)."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import ReminderHistory, AuditLog

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
            today = now.date()
            since_naive = (now - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)

            def _to_local_date(dt):
                if not dt:
                    return None
                if dt.tzinfo:
                    return dt.astimezone(tz).date()
                return dt.replace(tzinfo=timezone.utc).astimezone(tz).date()

            feito_today = feito_week = rem_today = rem_week = 0
            feito_by_day: dict[str, int] = {}
            rem_by_day: dict[str, int] = {}

            for a in db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.action == "list_feito",
                AuditLog.created_at >= since_naive,
            ).all():
                d = _to_local_date(a.created_at)
                if d:
                    feito_by_day[d.isoformat()] = feito_by_day.get(d.isoformat(), 0) + 1
                    if d == today:
                        feito_today += 1
                    if (today - d).days < 7:
                        feito_week += 1

            for r in db.query(ReminderHistory).filter(
                ReminderHistory.user_id == user.id,
                ReminderHistory.status == "sent",
                ReminderHistory.delivered_at.isnot(None),
                ReminderHistory.delivered_at >= since_naive,
            ).all():
                d = _to_local_date(r.delivered_at)
                if d:
                    rem_by_day[d.isoformat()] = rem_by_day.get(d.isoformat(), 0) + 1
                    if d == today:
                        rem_today += 1
                    if (today - d).days < 7:
                        rem_week += 1

            lines = ["📊 **Estatísticas**"]
            if mode == "resumo":
                lines.append(f"Hoje: {feito_today} tarefas feitas | {rem_today} lembretes")
                lines.append(f"Esta semana: {feito_week} tarefas | {rem_week} lembretes")
            elif mode == "dia":
                lines.append("Últimos 7 dias:")
                for i in range(6, -1, -1):
                    d = today - timedelta(days=i)
                    fd = feito_by_day.get(d.isoformat(), 0)
                    rd = rem_by_day.get(d.isoformat(), 0)
                    lines.append(f"• {d.strftime('%d/%m')} — {fd} tarefas | {rd} lembretes")
            elif mode == "semana":
                lines.append("Últimas 4 semanas:")
                for i in range(4):
                    start = today - timedelta(days=6 + i * 7)
                    end = today - timedelta(days=i * 7)
                    fd = sum(feito_by_day.get((today - timedelta(days=i * 7 + j)).isoformat(), 0) for j in range(7))
                    rd = sum(rem_by_day.get((today - timedelta(days=i * 7 + j)).isoformat(), 0) for j in range(7))
                    lines.append(f"• S{i + 1} ({start.strftime('%d/%m')}–{end.strftime('%d/%m')}): {fd} tarefas | {rd} lembretes")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar estatísticas: {e}"


async def handle_stats(ctx: "HandlerContext", content: str) -> str | None:
    """/stats ou /stats dia ou /stats semana. Aceita NL: stats, estatísticas."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip().lower()
    if not t.startswith("/stats"):
        return None
    rest = t[6:].strip()
    mode = "resumo"
    if rest == "dia":
        mode = "dia"
    elif rest == "semana":
        mode = "semana"
    return _visao_stats(ctx, mode)
