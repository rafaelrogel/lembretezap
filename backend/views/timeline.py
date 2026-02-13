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
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import Event, ReminderHistory, AuditLog

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
                    items.append((ts, f"Lembrete: {msg} ✓"))

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
                        items.append((ts, f"Feito: {a.resource or '?'}"))
                    elif a.action == "list_add":
                        items.append((ts, f"Add: {a.resource or '?'}"))
                    elif a.action == "list_remove":
                        items.append((ts, f"Removido: {a.resource or '?'}"))

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
                    nome = (ev.payload or {}).get("nome", "") if isinstance(ev.payload, dict) else str(ev.payload)[:40]
                    items.append((ts, f"Evento: {nome or ev.tipo}"))

            items.sort(key=lambda x: x[0], reverse=True)
            lines = [f"📜 **Timeline** (últimos {dias} dias)"]
            for ts, label in items[:25]:
                lines.append(f"• {ts.strftime('%d/%m %H:%M')} — {label}")
            if not items:
                lines.append("• Nada nos últimos dias.")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar timeline: {e}"


async def handle_timeline(ctx: "HandlerContext", content: str) -> str | None:
    """/timeline ou /timeline 14: histórico cronológico."""
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
