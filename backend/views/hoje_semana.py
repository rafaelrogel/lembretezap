"""Visão: /hoje, /semana, /agenda — /hoje mostra agenda + lembretes do dia; /semana só agenda da semana; /agenda só agenda do dia."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


from backend.views.utils import get_events_in_period, get_reminders_in_period


def _visao_hoje(ctx: "HandlerContext") -> str:
    """/hoje: agenda + lembretes do dia."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale)
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
            today = now.date()

            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
            period_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=tz)
            today_start_utc_ms = int(today_start.timestamp() * 1000)
            period_end_utc_ms = int(period_end.timestamp() * 1000)

            from backend.locale import VIEW_LABEL_HOJE
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            lines = [VIEW_LABEL_HOJE.get(lang, VIEW_LABEL_HOJE["en"])]

            # Lembretes do dia
            reminders = get_reminders_in_period(ctx, tz, today_start_utc_ms, period_end_utc_ms)
            from backend.locale import VIEW_REMINDERS_HEADER
            lines.append(VIEW_REMINDERS_HEADER.get(lang, VIEW_REMINDERS_HEADER["en"]))
            if reminders:
                for dt, msg in reminders[:15]:
                    lines.append(f"• {dt.strftime('%H:%M')} — {msg}")
            else:
                from backend.locale import VIEW_NO_REMINDERS_TODAY
                _lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                lines.append(VIEW_NO_REMINDERS_TODAY.get(_lang, VIEW_NO_REMINDERS_TODAY["en"]))

            # Agenda (eventos) do dia
            event_list = get_events_in_period(db, user.id, today, today, tz, lang=lang)
            from backend.locale import VIEW_AGENDA_HEADER
            lines.append(VIEW_AGENDA_HEADER.get(lang, VIEW_AGENDA_HEADER["en"]))
            date_fmt = "%Y-%m-%d" if lang == "en" else "%d/%m"
            if event_list:
                for d, _, nome in event_list[:15]:
                    lines.append(f"• {d.strftime(date_fmt)} — {nome}")
                # Oferecer criar lembrete antes do evento (ex.: 15 min antes)
                from backend.user_store import get_user_language
                from backend.locale import AGENDA_OFFER_REMINDER, resolve_response_language
                lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
                lines.append(AGENDA_OFFER_REMINDER.get(lang, AGENDA_OFFER_REMINDER["en"]))
            else:
                from backend.locale import VIEW_NO_EVENTS_TODAY
                _lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                lines.append(VIEW_NO_EVENTS_TODAY.get(_lang, VIEW_NO_EVENTS_TODAY["en"]))

            # Segunda vez que vê a agenda no mesmo dia: perguntar se já realizou e se quer remover
            from backend.agenda_view_tracker import record_agenda_view
            from backend.user_store import get_user_language
            from backend.locale import AGENDA_SECOND_VIEW_PROMPT, resolve_response_language

            count = record_agenda_view(ctx.chat_id, today.isoformat())
            if count >= 2:
                lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
                lines.append(AGENDA_SECOND_VIEW_PROMPT.get(lang, AGENDA_SECOND_VIEW_PROMPT["en"]))

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        from backend.locale import VIEW_ERROR
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)


def _visao_agenda_dia(ctx: "HandlerContext") -> str:
    """/agenda: apenas agenda (eventos) do dia corrente."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
    from backend.locale import AGENDA_OFFER_REMINDER, AGENDA_SECOND_VIEW_PROMPT, resolve_response_language
    from backend.agenda_view_tracker import record_agenda_view

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale)
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
            today = now.date()
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"

            from backend.locale import VIEW_AGENDA_TODAY_HEADER, VIEW_NO_EVENTS_WEEK, VIEW_ERROR
            lines = [VIEW_AGENDA_TODAY_HEADER.get(lang, VIEW_AGENDA_TODAY_HEADER["en"])]

            event_list = get_events_in_period(db, user.id, today, today, tz, lang=lang)
            date_fmt = "%Y-%m-%d" if lang == "en" else "%d/%m"
            if event_list:
                for d, _, nome in event_list[:15]:
                    lines.append(f"• {d.strftime(date_fmt)} — {nome}")

                lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
                lines.append(AGENDA_OFFER_REMINDER.get(lang, AGENDA_OFFER_REMINDER["en"]))
            else:
                from backend.locale import VIEW_NO_EVENTS_TODAY
                lines.append(VIEW_NO_EVENTS_TODAY.get(lang, VIEW_NO_EVENTS_TODAY["en"]))

            count = record_agenda_view(ctx.chat_id, today.isoformat())
            if count >= 2:
                lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
                lines.append(AGENDA_SECOND_VIEW_PROMPT.get(lang, AGENDA_SECOND_VIEW_PROMPT["en"]))

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        from backend.locale import VIEW_ERROR
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)


def _visao_semana(ctx: "HandlerContext") -> str:
    """/semana: apenas agenda (eventos) da semana; não mostra lembretes."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language

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

            try:
                from zapista.clock_drift import get_effective_time
                _now_ts = get_effective_time()
            except Exception:
                import time
                _now_ts = time.time()
            now = datetime.fromtimestamp(_now_ts, tz=tz)
            today = now.date()
            end_date = today + timedelta(days=6)  # 7 dias: hoje + 6

            from backend.locale import VIEW_AGENDA_WEEK_HEADER, VIEW_NO_EVENTS_WEEK
            lines = [VIEW_AGENDA_WEEK_HEADER.get(lang, VIEW_AGENDA_WEEK_HEADER["en"]).format(end_date=end_date.strftime('%d/%m'))]

            event_list = get_events_in_period(db, user.id, today, end_date, tz, lang=lang)
            date_fmt = "%Y-%m-%d" if lang == "en" else "%d/%m"
            if event_list:
                for d, _, nome in event_list[:25]:
                    lines.append(f"• {d.strftime(date_fmt)} — {nome}")
            else:
                lines.append(VIEW_NO_EVENTS_WEEK.get(lang, VIEW_NO_EVENTS_WEEK["en"]))

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        from backend.locale import VIEW_ERROR
        return VIEW_ERROR.get("pt-BR", VIEW_ERROR["en"]).format(error=e)


async def handle_hoje(ctx: "HandlerContext", content: str) -> str | None:
    """/hoje, /hoy, /today. Aceita NL: hoje, o que tenho hoje."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/hoje"):
        return None
    return _visao_hoje(ctx)


async def handle_semana(ctx: "HandlerContext", content: str) -> str | None:
    """/semana, /week. Aceita NL: semana, esta semana."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/semana"):
        return None
    return _visao_semana(ctx)


async def handle_agenda(ctx: "HandlerContext", content: str) -> str | None:
    """/agenda. Aceita NL: agenda, minha agenda, o que tenho agendado."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/agenda"):
        return None
    return _visao_agenda_dia(ctx)


# Frases em texto/áudio que mostram a agenda do dia (mesma visão e contagem que /agenda)
_AGENDA_NL_PHRASES = frozenset([
    "agenda", "minha agenda", "ver agenda", "mostra agenda", "mostrar agenda",
    "mostrar minha agenda", "mostrar a minha agenda", "mostre minha agenda", "mostre a minha agenda", "ver a minha agenda",
    "o que tenho hoje", "que tenho hoje", "o que tenho para hoje", "o que é hoje",
    "what do i have today", "my agenda", "show agenda", "today's agenda",
    "qué tengo hoy", "mi agenda", "agenda del día",
])


async def handle_agenda_nl(ctx: "HandlerContext", content: str) -> str | None:
    """Pedido por texto/áudio tipo 'minha agenda', 'o que tenho hoje' → mesma visão que /agenda (conta para 2.ª vez)."""
    t = (content or "").strip().lower()
    if not t or len(t) > 80:
        return None
    if t in _AGENDA_NL_PHRASES:
        return _visao_agenda_dia(ctx)
    # Frase curta que é só sobre agenda/hoje (ex.: "e a minha agenda?" após transcrição)
    t_clean = t.rstrip(".?!")
    if t_clean in _AGENDA_NL_PHRASES:
        return _visao_agenda_dia(ctx)
    return None
