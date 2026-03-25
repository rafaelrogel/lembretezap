"""Visão unificada: lembretes (cron) + listas (filmes, livros, músicas, etc.).
Nota: Agenda e eventos são sinónimos (compromissos com data/hora). Listas = filmes, livros, músicas, notas, sites, to-dos, etc.

Suporta qualificadores temporais ("para 2027", "this week", "en marzo") para filtrar por período.
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.handler_context import HandlerContext


def _is_eventos_unificado_intent(content: str) -> bool:
    """Detecta pedidos de visão unificada: lembretes + listas/agenda.

    Reconhece pedidos com ou sem qualificador temporal:
      - "meus lembretes"
      - "mostre meus lembretes para 2027"
      - "show my reminders for this week"
      - "mis recordatorios para marzo"
    """
    t = (content or "").strip().lower()
    # Exclude requests clearly about lists (compras, mercado, filmes, etc.)
    if re.search(r"\blista\s+de\s+(?:compras|mercado|filmes?|livros?|m[uú]sicas?|receitas?|notas?|tarefas?|pendentes)", t):
        return False
    if re.search(r"\b(?:minha|meu)\s+lista\b", t):
        return False

    patterns = [
        # PT: "meus lembretes", "meus eventos", "meus lembretes para 2027", "mostre meus lembretes para esta semana"
        r"meus?\s+eventos?",
        r"meus?\s+lembretes?",
        r"meus?\s+lembran[cç]as?",
        r"meus?\s+agendamentos?",
        r"o\s+que\s+tenho\s+agendado",
        r"lista\s+(de\s+)?(lembretes?|eventos?)",
        r"o\s+que\s+(tenho|est[aá]\s+agendado)",
        r"quais?\s+(s[aã]o\s+)?(os\s+)?(meus\s+)?(lembretes?|eventos?)",
        # PT: "mostre/ver/listar lembretes/eventos" (com ou sem qualificador)
        r"(?:mostr[ea]r?|ver|listar|exib[ai]r?)\s+(?:os?\s+)?(?:meus?\s+)?(?:lembretes?|eventos?|lembran[cç]as?|agendamentos?)",
        # EN: "my reminders", "show my reminders for 2027", "list my events"
        r"(?:show|list|display|view)\s+(?:my\s+)?(?:reminders?|events?|appointments?)",
        r"my\s+(?:reminders?|events?|appointments?)",
        r"what\s+(?:reminders?|events?|appointments?)\s+do\s+i\s+have",
        # ES: "mis recordatorios", "mostrar mis recordatorios para 2027", "mis eventos"
        r"(?:mostrar?|ver|listar|enseñar?)\s+(?:mis?\s+)?(?:recordatorios?|eventos?|citas?)",
        r"mis?\s+(?:recordatorios?|eventos?|citas?)",
        r"(?:qué|que)\s+(?:recordatorios?|eventos?|citas?)\s+tengo",
        # Generic agenda queries falling through /agenda (which is day-only) -> "agenda mês", "agenda 2028"
        r"agendas?\s+(?:.+$)",
        r"(?:calend[aá]rios?|calendars?|schedules?)\s+(?:.+$)",
    ]
    return any(re.search(p, t) for p in patterns)


def _get_user_tz_and_lang(ctx: HandlerContext) -> tuple[ZoneInfo, str]:
    """Helper to get user timezone and language."""
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone, get_user_language
    from backend.locale import resolve_response_language

    tz = ZoneInfo("UTC")
    lang = "pt-BR"
    try:
        db = SessionLocal()
        try:
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
            lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
        finally:
            db.close()
    except Exception:
        pass
    return tz, lang




async def handle_eventos_unificado(ctx: HandlerContext, content: str) -> str | None:
    """Visão unificada: lembretes (cron) + eventos da agenda.

    Suporta qualificadores temporais: filtra por período se detectado.
    Sem qualificador: mostra tudo.
    """
    if not _is_eventos_unificado_intent(content):
        return None

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    tz, lang = _get_user_tz_and_lang(ctx)

    # Parse period from content
    from backend.period_parser import parse_period, period_label

    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        import time as _time
        _now_ts = _time.time()

    now = datetime.fromtimestamp(_now_ts, tz=tz)
    today = now.date()

    res = parse_period(content, today=today)
    period = (res[0], res[1]) if res else None
    wd_filter = res[2] if res else None
    
    # If the user explicitly asked for a specific timeframe like "do biênio" but we couldn't parse it
    from backend.command_nl import normalize_nl_to_command
    original = normalize_nl_to_command(content)
    if not period and original.startswith("/agenda ") and len(original) > 8:
        _UNKNOWN_PERIOD = {
            "pt-BR": "Desculpa, não consegui entender o período que pediste (ex: 'este mês', 'esta semana' ou um ano específico).",
            "pt-PT": "Desculpa, não consegui perceber o período que pediste (ex: 'este mês', 'esta semana' ou um ano específico).",
            "es": "Lo siento, no pude entender el período que solicitaste (ej: 'este mes', 'esta semana' o un año específico).",
            "en": "Sorry, I couldn't understand the timeframe you requested (e.g., 'this month', 'this week', or a specific year)."
        }
        return _UNKNOWN_PERIOD.get(lang, _UNKNOWN_PERIOD["en"])

    parts = []

    # Header
    _HEADER_ALL = {
        "pt-BR": "📅 **Lembretes & Agenda ({tz})**",
        "pt-PT": "📅 **Lembretes & Agenda ({tz})**",
        "es":    "📅 **Recordatorios & Agenda ({tz})**",
        "en":    "📅 **Reminders & Agenda ({tz})**",
    }
    _HEADER_PERIOD = {
        "pt-BR": "📅 **Lembretes & Agenda — {period} ({tz})**",
        "pt-PT": "📅 **Lembretes & Agenda — {period} ({tz})**",
        "es":    "📅 **Recordatorios & Agenda — {period} ({tz})**",
        "en":    "📅 **Reminders & Agenda — {period} ({tz})**",
    }

    tz_name = str(tz)
    if period:
        start_d, end_d = period
        label = period_label(start_d, end_d, lang)
        
        # Se tem filtro de dia da semana, adicionar ao label
        if wd_filter is not None:
            _WD_LABELS = {
                "pt-BR": ["segundas", "terças", "quartas", "quintas", "sextas", "sábados", "domingos"],
                "pt-PT": ["segundas", "terças", "quartas", "quintas", "sextas", "sábados", "domingos"],
                "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"],
                "en": ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"],
            }
            wd_lbl = _WD_LABELS.get(lang, _WD_LABELS["en"])[wd_filter]
            label = f"{wd_lbl} ({label})"

        header = _HEADER_PERIOD.get(lang, _HEADER_PERIOD["en"]).format(period=label, tz=tz_name)
    else:
        header = _HEADER_ALL.get(lang, _HEADER_ALL["en"]).format(tz=tz_name)

    parts.append(header)

    # --- Lembretes (cron) ---
    _LBL_REMINDERS = {
        "pt-BR": "\n🔔 **Lembretes**",
        "pt-PT": "\n🔔 **Lembretes**",
        "es":    "\n🔔 **Recordatorios**",
        "en":    "\n🔔 **Reminders**",
    }
    _NO_REMINDERS = {
        "pt-BR": "• Nenhum lembrete agendado.",
        "pt-PT": "• Nenhum lembrete agendado.",
        "es":    "• Ningún recordatorio programado.",
        "en":    "• No reminders scheduled.",
    }
    _NO_REMINDERS_PERIOD = {
        "pt-BR": "• Nenhum lembrete neste período.",
        "pt-PT": "• Nenhum lembrete neste período.",
        "es":    "• Ningún recordatorio en este período.",
        "en":    "• No reminders in this period.",
    }

    if period:
        start_d, end_d = period
        from datetime import time as _time_cls
        start_dt = datetime.combine(start_d, _time_cls.min).replace(tzinfo=tz)
        end_dt = datetime.combine(end_d, _time_cls.max).replace(tzinfo=tz)
        start_utc_ms = int(start_dt.timestamp() * 1000)
        end_utc_ms = int(end_dt.timestamp() * 1000)

        from backend.views.utils import get_reminders_in_period
        reminders = get_reminders_in_period(ctx, tz, start_utc_ms, end_utc_ms)
        # Apply weekday filter manually since get_reminders_in_period doesn't support it yet
        if reminders and wd_filter is not None:
            reminders = [r for r in reminders if r[0].weekday() == wd_filter]

        parts.append(_LBL_REMINDERS.get(lang, _LBL_REMINDERS["en"]))
        if reminders:
            for dt, msg in reminders[:25]:
                parts.append(f"• {dt.strftime('%d/%m %H:%M')} — {msg[:50]}{'…' if len(msg) > 50 else ''}")
        else:
            parts.append(_NO_REMINDERS_PERIOD.get(lang, _NO_REMINDERS_PERIOD["en"]))
    else:
        # Sem período: listar todos (via cron_tool)
        if ctx.cron_tool:
            ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
            cron_out = await ctx.cron_tool.execute(action="list")
            if "Nenhum lembrete" not in cron_out and "No reminders" not in cron_out and "Ningún" not in cron_out:
                parts.append(cron_out)
            else:
                parts.append(_LBL_REMINDERS.get(lang, _LBL_REMINDERS["en"]))
                parts.append(_NO_REMINDERS.get(lang, _NO_REMINDERS["en"]))
        else:
            parts.append(_LBL_REMINDERS.get(lang, _LBL_REMINDERS["en"]))
            parts.append(_NO_REMINDERS.get(lang, _NO_REMINDERS["en"]))

    # --- Eventos da Agenda ---
    _LBL_EVENTS = {
        "pt-BR": "\n📆 **Agenda**",
        "pt-PT": "\n📆 **Agenda**",
        "es":    "\n📆 **Agenda**",
        "en":    "\n📆 **Events**",
    }
    _NO_EVENTS = {
        "pt-BR": "• Nenhum evento na agenda.",
        "pt-PT": "• Nenhum evento na agenda.",
        "es":    "• Ningún evento en la agenda.",
        "en":    "• No events in the agenda.",
    }
    _NO_EVENTS_PERIOD = {
        "pt-BR": "• Nenhum evento neste período.",
        "pt-PT": "• Nenhum evento neste período.",
        "es":    "• Ningún evento en este período.",
        "en":    "• No events in this period.",
    }

    try:
        from backend.database import SessionLocal
        from backend.user_store import get_or_create_user
        from backend.models_db import Event

        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)

            from backend.views.utils import get_events_in_period
            if period:
                start_d, end_d = period
                event_list = get_events_in_period(db, user.id, start_d, end_d, tz, lang=lang)
                if wd_filter is not None:
                    event_list = [e for e in event_list if e[0].weekday() == wd_filter]

                parts.append(_LBL_EVENTS.get(lang, _LBL_EVENTS["en"]))
                if event_list:
                    for d, dt_utc, nome, time_str in event_list[:25]:
                        dt_str = f"{d.strftime('%d/%m')} {time_str}" if time_str else d.strftime("%d/%m")
                        parts.append(f"• {dt_str} — {nome[:50]}")
                else:
                    parts.append(_NO_EVENTS_PERIOD.get(lang, _NO_EVENTS_PERIOD["en"]))
            else:
                # Sem período: listar eventos de hoje em diante (excluir passados)
                from datetime import time as _time_cls
                today_start_utc = datetime.combine(today, _time_cls.min).replace(tzinfo=tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
                events = db.query(Event).filter(
                    Event.user_id == user.id,
                    Event.tipo == "evento",
                    Event.deleted == False,
                    (Event.data_at >= today_start_utc) | (Event.data_at.is_(None)),
                ).all()

                parts.append(_LBL_EVENTS.get(lang, _LBL_EVENTS["en"]))
                if events:
                    for ev in events:
                        nome = ev.payload.get("nome", "Evento Desconhecido").strip()
                        if ev.data_at:
                            ev_local = ev.data_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                            if ev_local.time() != datetime.min.time():
                                dt_str = ev_local.strftime("%d/%m %H:%M")
                            else:
                                dt_str = ev_local.strftime("%d/%m")
                        else:
                            dt_str = "S/ Data"
                        parts.append(f"• {dt_str} — {nome}")
                else:
                    parts.append(_NO_EVENTS.get(lang, _NO_EVENTS["en"]))
        finally:
            db.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

    if len(parts) <= 1:
        _EMPTY_ALL = {
            "pt-BR": "📅 Não tens lembretes nem eventos agendados.",
            "pt-PT": "📅 Não tens lembretes nem eventos agendados.",
            "es":    "📅 No tienes recordatorios ni eventos programados.",
            "en":    "📅 You have no reminders or events scheduled.",
        }
        _EMPTY_PERIOD = {
            "pt-BR": "📅 Nenhum lembrete ou evento neste período.",
            "pt-PT": "📅 Nenhum lembrete ou evento neste período.",
            "es":    "📅 Ningún recordatorio o evento en este período.",
            "en":    "📅 No reminders or events in this period.",
        }
        if period:
            start_d, end_d = period
            label = period_label(start_d, end_d, lang)
            return f"📅 **{label}** — " + _EMPTY_PERIOD.get(lang, _EMPTY_PERIOD["en"])
            
        return _EMPTY_ALL.get(lang, _EMPTY_ALL["en"])

    return "\n".join(parts)
