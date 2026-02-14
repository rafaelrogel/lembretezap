"""Visão: /resumo (ou /revisao) — resumo da semana (tarefas, lembretes, eventos)."""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_revisao_semanal(ctx: "HandlerContext") -> str:
    """Resumo da semana (últimos 7 dias)."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language, get_user_preferred_name
    from backend.weekly_recap import get_week_stats, build_weekly_recap_text

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            today = datetime.now(tz).date()
            stats = get_week_stats(db, ctx.chat_id, today, tz)
            user_lang = get_user_language(db, ctx.chat_id)
            preferred_name = get_user_preferred_name(db, ctx.chat_id)
            return build_weekly_recap_text(
                stats=stats,
                user_lang=user_lang,
                preferred_name=preferred_name,
            )
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar revisão: {e}"


async def handle_revisao(ctx: "HandlerContext", content: str) -> str | None:
    """/resumo ou /revisao — resumo da semana."""
    t = content.strip().lower()
    if not (t.startswith("/resumo") or t.startswith("/revisao")):
        return None
    return _visao_revisao_semanal(ctx)
