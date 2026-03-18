"""Visão: /timeline — histórico cronológico de lembretes, tarefas, eventos."""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_timeline(ctx: "HandlerContext", dias: int = 7) -> str:
    """Histórico cronológico: lembretes entregues, tarefas feitas, eventos criados."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
    from backend.models_db import Event, ReminderHistory, AuditLog
    from backend.locale import (
        VIEW_TIMELINE_HEADER, VIEW_TIMELINE_TZ_INFO, VIEW_TIMELINE_REMINDER,
        VIEW_TIMELINE_DONE, VIEW_TIMELINE_REMOVED, VIEW_TIMELINE_EVENT,
        VIEW_TIMELINE_EMPTY, VIEW_ERROR, EVENT_CALENDAR_IMPORTED,
    )

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale)
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            since = now - timedelta(days=dias)
            since_naive = since.astimezone(timezone.utc).replace(tzinfo=None) if since.tzinfo else since

            items: list[tuple[datetime, str]] = []
            for r in (
                db.query(ReminderHistory)
                .filter(
                    ReminderHistory.user_id == user.id,
                    ReminderHistory.status == "sent",
                    ReminderHistory.delivered_at.isnot(None),
                    ReminderHistory.delivered_at >= since_naive,
                )
                .all()
            ):
                ts = r.delivered_at or r.created_at
                if ts:
                    if ts.tzinfo:
                        ts = ts.astimezone(tz)
                    else:
                        ts = ts.replace(tzinfo=timezone.utc).astimezone(tz)
                    msg = (r.message or "")[:45] + ("…" if len(r.message or "") > 45 else "")
                    items.append((ts, VIEW_TIMELINE_REMINDER.get(lang, VIEW_TIMELINE_REMINDER["en"]).format(msg=msg)))

            for a in (
                db.query(AuditLog)
                .filter(
                    AuditLog.user_id == user.id,
                    AuditLog.action.in_(("list_feito", "list_add", "list_remove")),
                    AuditLog.created_at >= since_naive,
                )
                .all()
            ):
                ts = a.created_at
                if ts and ts.tzinfo:
                    ts = ts.astimezone(tz)
                elif ts:
                    ts = ts.replace(tzinfo=timezone.utc).astimezone(tz)
                if ts:
                    if a.action == "list_feito":
                        items.append((ts, VIEW_TIMELINE_DONE.get(lang, VIEW_TIMELINE_DONE["en"]).format(resource=a.resource or '?')))
                    elif a.action == "list_add":
                        items.append((ts, f"Add: {a.resource or '?'}"))
                    elif a.action == "list_remove":
                        items.append((ts, VIEW_TIMELINE_REMOVED.get(lang, VIEW_TIMELINE_REMOVED["en"]).format(resource=a.resource or '?')))

            for ev in (
                db.query(Event)
                .filter(Event.user_id == user.id, Event.deleted == False, Event.created_at >= since_naive)
                .all()
            ):
                ts = ev.created_at
                if ts and ts.tzinfo:
                    ts = ts.astimezone(tz)
                elif ts:
                    ts = ts.replace(tzinfo=timezone.utc).astimezone(tz)
                if ts:
                    pl = ev.payload if isinstance(ev.payload, dict) else {}
                    nome = pl.get("nome", "") or (str(ev.payload)[:40] if ev.payload else ev.tipo)
                    from_ics = EVENT_CALENDAR_IMPORTED.get(lang, EVENT_CALENDAR_IMPORTED["en"]) if pl.get("source") == "ics" else ""
                    items.append((ts, VIEW_TIMELINE_EVENT.get(lang, VIEW_TIMELINE_EVENT["en"]).format(from_ics=from_ics, name=nome)))

            items.sort(key=lambda x: x[0], reverse=True)
            lines = [VIEW_TIMELINE_HEADER.get(lang, VIEW_TIMELINE_HEADER["en"]).format(days=dias)]
            lines.append(VIEW_TIMELINE_TZ_INFO.get(lang, VIEW_TIMELINE_TZ_INFO["en"]).format(tz=tz_iana))
            for ts, label in items[:25]:
                lines.append(f"• {ts.strftime('%d/%m %H:%M')} — {label}")
            if not items:
                lines.append(VIEW_TIMELINE_EMPTY.get(lang, VIEW_TIMELINE_EMPTY["en"]))
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)


async def handle_timeline(ctx: "HandlerContext", content: str) -> str | None:
    """/timeline ou /timeline 14. Aceita NL: timeline, cronologia, linha do tempo."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip().lower()
    if not t.startswith("/timeline"):
        return None
    rest = t[9:].strip()
    dias = 7
    if rest:
        m = re.match(r"^(\d+)\s*$", rest)
        if m:
            dias = min(30, max(1, int(m.group(1))))
    return _visao_timeline(ctx, dias)
