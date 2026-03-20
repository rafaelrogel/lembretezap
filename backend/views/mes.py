"""Visão: /mes — calendário ASCII do mês com marcadores nos dias com atividade."""

import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _visao_mes(ctx: "HandlerContext", year: int, month: int) -> str:
    """Visão de lista filtrada pelo mês (agenda e lembretes)."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
    from backend.locale import (
        VIEW_MONTH_NAMES, VIEW_ERROR, VIEW_AGENDA_MONTH_HEADER,
        VIEW_NO_EVENTS_MONTH, VIEW_REMINDERS_MONTH_HEADER, VIEW_NO_REMINDERS_MONTH
    )
    from backend.views.utils import get_events_in_period, get_reminders_in_period

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

            first_day = datetime(year, month, 1).date()
            _, last_dom = calendar.monthrange(year, month)
            last_day = datetime(year, month, last_dom).date()

            start_utc_ms = int(datetime(year, month, 1, 0, 0, 0, tzinfo=tz).timestamp() * 1000)
            end_utc_ms = int(datetime(year, month, last_dom, 23, 59, 59, tzinfo=tz).timestamp() * 1000)

            _mnames = VIEW_MONTH_NAMES.get(lang, VIEW_MONTH_NAMES["en"])
            month_name = _mnames[month - 1]

            lines = []
            
            # Agenda
            event_list = get_events_in_period(db, user.id, first_day, last_day, tz, lang=lang)
            header_agenda = VIEW_AGENDA_MONTH_HEADER.get(lang, VIEW_AGENDA_MONTH_HEADER["en"]).format(month=month_name, year=year)
            lines.append(header_agenda)
            
            date_fmt = "%Y-%m-%d" if lang == "en" else "%d/%m"
            if event_list:
                for d, _, nome in event_list:
                    lines.append(f"• {d.strftime(date_fmt)} — {nome}")
            else:
                lines.append(VIEW_NO_EVENTS_MONTH.get(lang, VIEW_NO_EVENTS_MONTH["en"]))

            # Lembretes
            reminders = get_reminders_in_period(ctx, tz, start_utc_ms, end_utc_ms)
            header_reminders = VIEW_REMINDERS_MONTH_HEADER.get(lang, VIEW_REMINDERS_MONTH_HEADER["en"]).format(month=month_name, year=year)
            lines.append(header_reminders)

            if reminders:
                for dt, msg in reminders:
                    lines.append(f"• {dt.strftime(date_fmt + ' %H:%M')} — {msg}")
            else:
                lines.append(VIEW_NO_REMINDERS_MONTH.get(lang, VIEW_NO_REMINDERS_MONTH["en"]))

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)
    except Exception as e:
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)


async def handle_mes(ctx: "HandlerContext", content: str) -> str | None:
    """/mes ou /mes 3 ou /mes 2026-03. Aceita NL: mês, mes, month."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    t = content.strip().lower()
    # Aceitar /mes ou /mês (com ou sem acento)
    if not (t.startswith("/mes") or t.startswith("/mês")):
        return None
        
    rest = t.split(maxsplit=1)[1] if " " in t else ""
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
