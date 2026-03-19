"""Handlers for date/time display: /hora, /data."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


async def handle_hora_data(ctx: "HandlerContext", content: str) -> str | None:
    """/hora ou /data. Mostra data/hora atual no timezone do usuário."""
    from backend.command_parser import parse
    from backend.database import SessionLocal
    from backend.user_store import get_user_timezone, get_user_language
    from zoneinfo import ZoneInfo
    from datetime import datetime
    intent = parse(content)
    if not intent or intent.get("type") not in ("hora", "data"):
        return None

    tz_iana = "UTC"
    lang = "pt-BR"
    try:
        db = SessionLocal()
        try:
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        finally:
            db.close()
    except Exception:
        pass

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

    now = datetime.fromtimestamp(_now_ts, tz=tz)

    if intent["type"] == "hora":
        msg = {
            "pt-PT": f"Agora são {now.strftime('%H:%M')}. 🕒",
            "pt-BR": f"Agora são {now.strftime('%H:%M')}. 🕒",
            "es": f"Ahora son las {now.strftime('%H:%M')}. 🕒",
            "en": f"It is currently {now.strftime('%H:%M')}. 🕒",
        }
    else:
        from backend.locale import resolve_response_language
        lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
        if lang == "en":
            fmt = "%Y-%m-%d"
        else:
            fmt = "%d/%m/%Y"
        msg = {
            "pt-PT": f"Hoje é dia {now.strftime(fmt)}. 📅",
            "pt-BR": f"Hoje é dia {now.strftime(fmt)}. 📅",
            "es": f"Hoy es {now.strftime(fmt)}. 📅",
            "en": f"Today is {now.strftime(fmt)}. 📅",
        }
    return msg.get(lang, msg["en"])
