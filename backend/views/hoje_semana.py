"""Visão: /hoje, /semana, /agenda — /hoje mostra agenda + lembretes do dia; /semana só agenda da semana; /agenda só agenda do dia."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _events_in_period(db, user_id: int, today, end_date, tz) -> list:
    """Eventos (agenda) do user no intervalo [today, end_date]."""
    from backend.models_db import Event

    events = db.query(Event).filter(
        Event.user_id == user_id,
        Event.deleted == False,
        Event.data_at.isnot(None),
    ).all()
    out = []
    seen = set()
    for ev in events:
        if not ev.data_at:
            continue
        ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
        try:
            ev_local = ev_date.astimezone(tz).date()
        except Exception:
            ev_local = ev_date.date()
        if today <= ev_local <= end_date:
            nome = (ev.payload or {}).get("nome", "") if isinstance(ev.payload, dict) else str(ev.payload)
            nome = (nome or "Evento").strip()
            
            # Deduplicação: ignorar se já vimos (data, nome_lower)
            key = (ev_local, nome.lower())
            if key in seen:
                continue
            seen.add(key)
            
            out.append((ev_local, ev.data_at, nome[:40]))
    out.sort(key=lambda x: (x[0], x[1] or datetime.min))
    return out


def _reminders_today(ctx: "HandlerContext", tz, today_start_utc_ms: int, period_end_utc_ms: int) -> list:
    """Lembretes (cron) do chat no intervalo [today_start_utc_ms, period_end_utc_ms]."""
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
    return reminders


def _visao_hoje(ctx: "HandlerContext") -> str:
    """/hoje: agenda + lembretes do dia."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
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

            lines = ["📅 **Hoje**"]

            # Lembretes do dia
            reminders = _reminders_today(ctx, tz, today_start_utc_ms, period_end_utc_ms)
            lines.append("\n🔔 **Lembretes**")
            if reminders:
                for dt, msg in reminders[:15]:
                    lines.append(f"• {dt.strftime('%H:%M')} — {msg[:50]}{'…' if len(msg) > 50 else ''}")
            else:
                lines.append("• Nenhum lembrete agendado para hoje.")

            # Agenda (eventos) do dia
            event_list = _events_in_period(db, user.id, today, today, tz)
            lines.append("\n📆 **Agenda**")
            if event_list:
                for d, _, nome in event_list[:15]:
                    lines.append(f"• {d.strftime('%d/%m')} — {nome[:50]}")
                # Oferecer criar lembrete antes do evento (ex.: 15 min antes)
                from backend.user_store import get_user_language
                from backend.locale import AGENDA_OFFER_REMINDER, resolve_response_language
                lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, None)
                lines.append(AGENDA_OFFER_REMINDER.get(lang, AGENDA_OFFER_REMINDER["en"]))
            else:
                lines.append("• Nenhum evento hoje.")

            # Segunda vez que vê a agenda no mesmo dia: perguntar se já realizou e se quer remover
            from backend.agenda_view_tracker import record_agenda_view
            from backend.user_store import get_user_language
            from backend.locale import AGENDA_SECOND_VIEW_PROMPT, resolve_response_language

            count = record_agenda_view(ctx.chat_id, today.isoformat())
            if count >= 2:
                lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, None)
                lines.append(AGENDA_SECOND_VIEW_PROMPT.get(lang, AGENDA_SECOND_VIEW_PROMPT["en"]))

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar visão: {e}"


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
            tz_iana = get_user_timezone(db, ctx.chat_id)
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

            lines = ["📆 **Agenda — hoje**"]

            event_list = _events_in_period(db, user.id, today, today, tz)
            if event_list:
                for d, _, nome in event_list[:15]:
                    lines.append(f"• {d.strftime('%d/%m')} — {nome[:50]}")
                lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, None)
                lines.append(AGENDA_OFFER_REMINDER.get(lang, AGENDA_OFFER_REMINDER["en"]))
            else:
                lines.append("• Nenhum evento hoje.")

            count = record_agenda_view(ctx.chat_id, today.isoformat())
            if count >= 2:
                lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                lang = resolve_response_language(lang, ctx.chat_id, None)
                lines.append(AGENDA_SECOND_VIEW_PROMPT.get(lang, AGENDA_SECOND_VIEW_PROMPT["en"]))

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar visão: {e}"


def _visao_semana(ctx: "HandlerContext") -> str:
    """/semana: apenas agenda (eventos) da semana; não mostra lembretes."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
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

            lines = [f"📆 **Agenda — esta semana** (até {end_date.strftime('%d/%m')})"]

            event_list = _events_in_period(db, user.id, today, end_date, tz)
            if event_list:
                for d, _, nome in event_list[:25]:
                    lines.append(f"• {d.strftime('%d/%m')} — {nome[:50]}")
            else:
                lines.append("• Nenhum evento esta semana.")

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar visão: {e}"


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
