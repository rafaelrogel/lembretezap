"""Handlers de comandos EXATAMENTE como no README: /lembrete, /list nome add item, /feito nome id.

- Sem botões interativos (sem Business API): confirmações com texto "1=sim 2=não".
- TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']).
- Persistência em SQLite (user_phone → listas/lembretes) via backend.models_db e cron.
- Baileys via gateway: resposta em texto (client.sendMessage(jid, {text: msg})).
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from zapista.agent.tools.cron import CronTool
    from zapista.agent.tools.list_tool import ListTool
    from zapista.cron.service import CronService

from backend.handler_context import HandlerContext, _reply_confirm_prompt
from backend.reminder_keywords import ALL_REMINDER_KEYWORDS


def _append_tz_hint_if_needed(reply: str, chat_id: str, phone_for_locale: str | None = None) -> str:
    """Se o timezone não foi informado pelo cliente, acrescenta dica para /tz Cidade."""
    if not reply or not reply.strip():
        return reply
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_timezone_and_source, get_user_language
        from backend.locale import TZ_HINT_SET_CITY, resolve_response_language
        db = SessionLocal()
        try:
            _, source = get_user_timezone_and_source(db, chat_id, phone_for_locale)
            if source == "db":
                return reply
            lang = get_user_language(db, chat_id, phone_for_locale) or "en"
            lang = resolve_response_language(lang, chat_id, phone_for_locale)
            hint = TZ_HINT_SET_CITY.get(lang, TZ_HINT_SET_CITY["en"])
            return f"{reply.strip()}\n\n{hint}"
        finally:
            db.close()
    except Exception:
        return reply


# ---------------------------------------------------------------------------
# Confirmação de oferta pendente: «Quero sim» após oferta de lembrete — Mimo
# ---------------------------------------------------------------------------

async def handle_pending_confirmation(ctx: HandlerContext, content: str) -> str | None:
    """
    Após «Quando quer o lembrete?»: trata confirmação («sim», «ok») ou resposta com tempo
    («a cada 30 min», «todo dia às 8h»). Usa Mimo para extrair params e criar o cron.
    """
    from backend.pending_confirmation import (
        looks_like_confirmation,
        looks_like_time_response,
        last_assistant_asked_when,
        try_extract_pending_cron,
        try_extract_time_response_cron,
    )

    if not (looks_like_confirmation(content) or looks_like_time_response(content)):
        return None
    if not ctx.cron_tool or not ctx.session_manager or not ctx.scope_provider or not ctx.scope_model:
        return None

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    history = session.get_history(max_messages=10)
    if len(history) < 2:
        return None

    last_assistant = None
    for m in reversed(history):
        if m.get("role") == "assistant":
            last_assistant = (m.get("content") or "").strip()
            break
    if not last_assistant_asked_when(last_assistant or ""):
        return None

    if looks_like_time_response(content):
        params = await try_extract_time_response_cron(
            ctx.scope_provider, ctx.scope_model, history, content
        )
    else:
        params = await try_extract_pending_cron(
            ctx.scope_provider, ctx.scope_model, history, content
        )
    if not params:
        return None

    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    msg_text = (params.get("message") or "").strip()
    if not msg_text:
        return None
    every = params.get("every_seconds")
    in_sec = params.get("in_seconds")
    cron_expr = params.get("cron_expr")
    result = await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        every_seconds=every,
        in_seconds=in_sec,
        cron_expr=cron_expr,
    )
    return _append_tz_hint_if_needed(result, ctx.chat_id, ctx.phone_for_locale)


# ---------------------------------------------------------------------------
# Fluxo de clarificação: evento + tempo vago (ex: "ir ao médico amanhã")
# ---------------------------------------------------------------------------

async def handle_vague_time_reminder(ctx: HandlerContext, content: str) -> str | None:
    """
    Quando o utilizador indica evento com data mas sem hora (ex: "tenho consulta amanhã"):
    1. Perguntar "A que horas é a sua consulta?"
    2. "15h" → perguntar "Quer ser lembrado com antecedência ou apenas na hora?"
    3. Se antecedência: "30 min" → agendar 2 lembretes (aviso + na hora).
    """
    import re
    from backend.reminder_flow import (
        FLOW_KEY,
        STAGE_NEED_TIME,
        STAGE_NEED_DATE,
        STAGE_NEED_ADVANCE_PREFERENCE,
        STAGE_NEED_ADVANCE_AMOUNT,
        is_vague_time_reminder,
        is_vague_date_reminder,
        parse_time_from_response,
        parse_date_from_response,
        parse_advance_seconds,
        looks_like_advance_preference_yes,
        looks_like_advance_preference_no,
        looks_like_no_reminder_at_all,
        is_consulta_context,
        compute_in_seconds_from_date_hour,
    )
    from backend.reminder_flow import MAX_RETRIES
    from backend.locale import (
        LangCode,
        REMINDER_ASK_TIME_CONSULTA,
        REMINDER_ASK_TIME_GENERIC,
        REMINDER_ASK_DATE_CONSULTA,
        REMINDER_ASK_DATE_GENERIC,
        REMINDER_ASK_ADVANCE_PREFERENCE,
        REMINDER_ASK_ADVANCE_AMOUNT,
        REMINDER_ASK_AGAIN,
        REMINDER_RETRY_SUFFIX,
        REMINDER_FAILED_NO_INFO,
        EVENT_REGISTERED_NO_REMINDER,
        PROACTIVE_NUDGE_12H_MSG,
    )
    from backend.user_store import get_user_language, get_user_timezone
    from backend.database import SessionLocal
    from backend.locale import resolve_response_language

    if not ctx.session_manager or not ctx.cron_tool or not content or not content.strip():
        return None

    # --- Cancelar fluxo se o usuário pedir (esc, cancel, sair, stop) ---
    t_clean = content.strip().lower()
    if t_clean in ("esc", "cancel", "cancelar", "sair", "stop", "para", "parar", "nvm"):
        session_key = f"{ctx.channel}:{ctx.chat_id}"
        session = ctx.session_manager.get_or_create(session_key)
        if session.metadata.get(FLOW_KEY):
            session.metadata.pop(FLOW_KEY, None)
            ctx.session_manager.save(session)
            # Retornar uma confirmação discreta ou deixar o Agente lidar?
            # Se retornarmos None, o Agente assume a mensagem.
            # Mas aqui queremos confirmar que o fluxo "parou".
            return "Ok, cancelado. 👍" if user_lang.startswith("pt") else ("Vale, cancelado. 👍" if user_lang == "es" else "Okay, cancelled. 👍")

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    flow = session.metadata.get(FLOW_KEY)

    # Normalizar: /lembrete X → X
    text = content.strip()
    if re.match(r"^/lembrete\s+", text, re.I):
        text = re.sub(r"^/lembrete\s+", "", text, flags=re.I).strip()

    user_lang: LangCode = "pt-BR"
    tz_iana = "UTC"
    try:
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, ctx.phone_for_locale)
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz_iana)
            except Exception:
                from backend.timezone import phone_to_default_timezone
                tz_iana = phone_to_default_timezone(ctx.phone_for_locale or ctx.chat_id)
        finally:
            db.close()
    except Exception:
        pass

    # Fallback: se timezone ficou UTC, usar fuso padrão do idioma (chat_id pode ser LID sem dígitos)
    from backend.timezone import DEFAULT_TZ_BY_LANG
    if tz_iana == "UTC" and user_lang in DEFAULT_TZ_BY_LANG:
        tz_iana = DEFAULT_TZ_BY_LANG[user_lang]

    # #region agent log
    try:
        import json as _j
        _log_path = r"C:\Users\rafae\.nanobot\.cursor\debug.log"
        open(_log_path, "a", encoding="utf-8").write(_j.dumps({"location": "handlers.handle_vague_time_reminder.tz", "message": "tz_iana set", "data": {"tz_iana": tz_iana, "chat_id_prefix": (ctx.chat_id or "")[:24]}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H1"}) + "\n")
    except Exception:
        pass
    # #endregion

    def _retry_or_fail(flow: dict, current_question: str) -> str | None:
        """Incrementa retry_count; se >= MAX_RETRIES, desiste e retorna REMINDER_FAILED_NO_INFO."""
        retry = flow.get("retry_count", 0) + 1
        if retry >= MAX_RETRIES:
            session.metadata.pop(FLOW_KEY, None)
            ctx.session_manager.save(session)
            return REMINDER_FAILED_NO_INFO.get(user_lang, REMINDER_FAILED_NO_INFO["en"])
        flow["retry_count"] = retry
        session.metadata[FLOW_KEY] = flow
        ctx.session_manager.save(session)
        suffix = REMINDER_RETRY_SUFFIX.get(user_lang, REMINDER_RETRY_SUFFIX["en"]).format(n=retry)
        return f"{current_question}\n\n{REMINDER_ASK_AGAIN.get(user_lang, REMINDER_ASK_AGAIN['en'])}{suffix}"

    # --- Estamos no fluxo: processar resposta ---
    if flow and isinstance(flow, dict):
        stage = flow.get("stage")
        msg_content = (flow.get("content") or "").strip()
        date_label = (flow.get("date_label") or "").strip()

        if stage == STAGE_NEED_DATE:
            parsed_date = parse_date_from_response(text)
            if parsed_date:
                hour = flow.get("hour", 0)
                minute = flow.get("minute", 0)
                in_sec = compute_in_seconds_from_date_hour(parsed_date, hour, minute, tz_iana)
                if in_sec and in_sec > 0:
                    session.metadata[FLOW_KEY] = {
                        "stage": STAGE_NEED_ADVANCE_PREFERENCE,
                        "content": msg_content,
                        "date_label": parsed_date,
                        "hour": hour,
                        "minute": minute,
                        "in_seconds": in_sec,
                        "retry_count": 0,
                    }
                    ctx.session_manager.save(session)
                    return REMINDER_ASK_ADVANCE_PREFERENCE.get(user_lang, REMINDER_ASK_ADVANCE_PREFERENCE["en"])
            q = REMINDER_ASK_DATE_CONSULTA.get(user_lang) if is_consulta_context(msg_content) else REMINDER_ASK_DATE_GENERIC.get(user_lang)
            return _retry_or_fail(flow, q)

        if stage == STAGE_NEED_TIME:
            parsed = parse_time_from_response(text)
            if parsed:
                hour, minute = parsed
                in_sec = compute_in_seconds_from_date_hour(date_label, hour, minute, tz_iana)
                # #region agent log
                try:
                    import json as _j
                    _log_path = r"C:\Users\rafae\.nanobot\.cursor\debug.log"
                    open(_log_path, "a", encoding="utf-8").write(_j.dumps({"location": "handlers.STAGE_NEED_TIME.after_compute", "message": "computed in_sec", "data": {"tz_iana": tz_iana, "date_label": date_label, "hour": hour, "minute": minute, "in_sec": in_sec, "chat_id_prefix": (ctx.chat_id or "")[:24]}, "timestamp": __import__("time").time() * 1000, "hypothesisId": "H3"}) + "\n")
                except Exception:
                    pass
                # #endregion
                if in_sec and in_sec > 0:
                    session.metadata[FLOW_KEY] = {
                        "stage": STAGE_NEED_ADVANCE_PREFERENCE,
                        "content": msg_content,
                        "date_label": date_label,
                        "hour": hour,
                        "minute": minute,
                        "in_seconds": in_sec,
                        "retry_count": 0,
                    }
                    ctx.session_manager.save(session)
                    return REMINDER_ASK_ADVANCE_PREFERENCE.get(user_lang, REMINDER_ASK_ADVANCE_PREFERENCE["en"])
            q = REMINDER_ASK_TIME_CONSULTA.get(user_lang) if is_consulta_context(msg_content) else REMINDER_ASK_TIME_GENERIC.get(user_lang)
            return _retry_or_fail(flow, q)

        elif stage == STAGE_NEED_ADVANCE_PREFERENCE:
            if looks_like_no_reminder_at_all(text):
                # Cliente não quer NENHUM lembrete; evento já está na agenda. Nudge proativo 12h antes se evento importante.
                session.metadata.pop(FLOW_KEY, None)
                ctx.session_manager.save(session)
                in_sec = flow.get("in_seconds")
                event_name = (flow.get("content") or msg_content or "").strip()
                try:
                    from backend.proactive_nudge_events import is_important_event_for_proactive_nudge
                    import time
                    from zapista.cron.types import CronSchedule
                    if event_name and in_sec and in_sec > 12 * 3600 and ctx.cron_service and is_important_event_for_proactive_nudge(event_name):
                        try:
                            from zapista.clock_drift import get_effective_time_ms
                            at_ms = get_effective_time_ms() + (in_sec - 12 * 3600) * 1000
                        except Exception:
                            at_ms = int(time.time() * 1000) + (in_sec - 12 * 3600) * 1000
                        nudge_msg = (PROACTIVE_NUDGE_12H_MSG.get(user_lang, PROACTIVE_NUDGE_12H_MSG["en"])).format(event_name=event_name)
                        ctx.cron_service.add_job(
                            name=(event_name[:26] + " (nudge)"),
                            schedule=CronSchedule(kind="at", at_ms=at_ms),
                            message=nudge_msg,
                            deliver=True,
                            channel=ctx.channel,
                            to=ctx.chat_id,
                            phone_for_locale=getattr(ctx, "phone_for_locale", None),
                            delete_after_run=True,
                            is_proactive_nudge=True,
                        )
                except Exception:
                    pass
                return EVENT_REGISTERED_NO_REMINDER.get(user_lang, EVENT_REGISTERED_NO_REMINDER["en"])

            if looks_like_advance_preference_no(text):
                # Só na hora → criar 1 lembrete
                in_sec = flow.get("in_seconds")
                if in_sec and in_sec > 0:
                    session.metadata.pop(FLOW_KEY, None)
                    ctx.session_manager.save(session)
                    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
                    result = await ctx.cron_tool.execute(
                        action="add",
                        message=msg_content,
                        in_seconds=in_sec,
                    )
                    return _append_tz_hint_if_needed(result, ctx.chat_id, ctx.phone_for_locale)

            if looks_like_advance_preference_yes(text):
                session.metadata[FLOW_KEY] = {
                    **flow,
                    "stage": STAGE_NEED_ADVANCE_AMOUNT,
                }
                ctx.session_manager.save(session)
                return REMINDER_ASK_ADVANCE_AMOUNT.get(user_lang, REMINDER_ASK_ADVANCE_AMOUNT["en"])

            # Tentar parse direto (ex: "30 min" como resposta)
            advance_sec = parse_advance_seconds(text)
            if advance_sec:
                in_sec = flow.get("in_seconds")
                if in_sec and in_sec > 0:
                    session.metadata.pop(FLOW_KEY, None)
                    ctx.session_manager.save(session)
                    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
                    # 2 lembretes: aviso (in_sec - advance_sec) e na hora (in_sec)
                    advance_in_sec = max(60, in_sec - advance_sec)
                    from backend.locale import REMINDER_ADVANCE_NOTICE_PREFIX
                    prefix = REMINDER_ADVANCE_NOTICE_PREFIX.get(user_lang, REMINDER_ADVANCE_NOTICE_PREFIX["en"])
                    r1 = await ctx.cron_tool.execute(
                        action="add",
                        message=f"{prefix} {msg_content}",
                        in_seconds=advance_in_sec,
                    )
                    r2 = await ctx.cron_tool.execute(
                        action="add",
                        message=msg_content,
                        in_seconds=in_sec,
                    )
                    out = f"{r1}\n\n{r2}" if r1 and r2 else (r1 or r2)
                    return _append_tz_hint_if_needed(out, ctx.chat_id)

            q = REMINDER_ASK_ADVANCE_PREFERENCE.get(user_lang, REMINDER_ASK_ADVANCE_PREFERENCE["en"])
            return _retry_or_fail(flow, q)

        elif stage == STAGE_NEED_ADVANCE_AMOUNT:
            advance_sec = parse_advance_seconds(text)
            if advance_sec:
                in_sec = flow.get("in_seconds")
                if in_sec and in_sec > 0:
                    session.metadata.pop(FLOW_KEY, None)
                    ctx.session_manager.save(session)
                    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
                    advance_in_sec = max(60, in_sec - advance_sec)
                    from backend.locale import REMINDER_ADVANCE_NOTICE_PREFIX
                    prefix = REMINDER_ADVANCE_NOTICE_PREFIX.get(user_lang, REMINDER_ADVANCE_NOTICE_PREFIX["en"])
                    r1 = await ctx.cron_tool.execute(
                        action="add",
                        message=f"{prefix} {msg_content}",
                        in_seconds=advance_in_sec,
                    )
                    r2 = await ctx.cron_tool.execute(
                        action="add",
                        message=msg_content,
                        in_seconds=in_sec,
                    )
                    out = f"{r1}\n\n{r2}" if r1 and r2 else (r1 or r2)
                    return _append_tz_hint_if_needed(out, ctx.chat_id)

            q = REMINDER_ASK_ADVANCE_AMOUNT.get(user_lang, REMINDER_ASK_ADVANCE_AMOUNT["en"])
            return _retry_or_fail(flow, q)

        # Fallback: resposta inválida em stage desconhecido
        return None

    # --- Novo pedido com evento + data + hora completos (ex.: "preciso ir ao médico amanhã às 17h") → agenda + perguntar lembrete ---
    if flow is None:
        from backend.reminder_flow import (
            parse_full_event_datetime,
            has_full_event_datetime,
        )
        from backend.models_db import Event, AuditLog
        from backend.database import SessionLocal
        from backend.user_store import get_or_create_user

        if has_full_event_datetime(text):
            parsed = parse_full_event_datetime(text, tz_iana)
            if parsed:
                content_ev, in_sec, data_at = parsed
                db_ev = SessionLocal()
                try:
                    user_ev = get_or_create_user(db_ev, ctx.chat_id)
                    from backend.limits import check_event_limits, LIMIT_EVENTS_PER_DAY
                    from backend.locale import (
                        LIMIT_AGENDA_PER_DAY_REACHED,
                        LIMIT_TOTAL_PER_DAY_REACHED,
                        LIMIT_WARNING_70,
                    )
                    target_date = data_at.date() if hasattr(data_at, "date") else data_at
                    if hasattr(data_at, "astimezone"):
                        from zoneinfo import ZoneInfo
                        target_date = data_at.astimezone(ZoneInfo(tz_iana)).date()
                    allowed, at_warning, ev_count, _, _ = check_event_limits(
                        db_ev, user_ev.id, target_date, tz_iana,
                        cron_service=ctx.cron_service, chat_id=ctx.chat_id,
                    )
                    if not allowed:
                        if ev_count >= LIMIT_EVENTS_PER_DAY:
                            return LIMIT_AGENDA_PER_DAY_REACHED.get(user_lang, LIMIT_AGENDA_PER_DAY_REACHED["en"])
                        return LIMIT_TOTAL_PER_DAY_REACHED.get(user_lang, LIMIT_TOTAL_PER_DAY_REACHED["en"])
                    ev = Event(
                        user_id=user_ev.id,
                        tipo="evento",
                        payload={"nome": content_ev},
                        data_at=data_at,
                        deleted=False,
                    )
                    db_ev.add(ev)
                    db_ev.add(AuditLog(user_id=user_ev.id, action="event_add", resource="evento"))
                    db_ev.commit()
                finally:
                    db_ev.close()
                session.metadata[FLOW_KEY] = {
                    "stage": STAGE_NEED_ADVANCE_PREFERENCE,
                    "content": content_ev,
                    "in_seconds": in_sec,
                    "retry_count": 0,
                }
                ctx.session_manager.save(session)
                from backend.locale import EVENT_REGISTERED_ASK_REMINDER
                out = EVENT_REGISTERED_ASK_REMINDER.get(user_lang, EVENT_REGISTERED_ASK_REMINDER["en"])
                if at_warning:
                    out += "\n\n" + LIMIT_WARNING_70.get(user_lang, LIMIT_WARNING_70["en"])
                return out

    # --- Novo pedido com tempo vago (data sem hora) ---
    ok, msg_content, date_label = is_vague_time_reminder(text)
    if ok:
        session.metadata[FLOW_KEY] = {
            "stage": STAGE_NEED_TIME,
            "content": msg_content,
            "date_label": date_label,
            "retry_count": 0,
        }
        ctx.session_manager.save(session)
        if is_consulta_context(msg_content):
            return REMINDER_ASK_TIME_CONSULTA.get(user_lang, REMINDER_ASK_TIME_CONSULTA["en"])
        return REMINDER_ASK_TIME_GENERIC.get(user_lang, REMINDER_ASK_TIME_GENERIC["en"])

    # --- Novo pedido com data vaga (hora sem data) ---
    ok2, msg_content2, hour, minute = is_vague_date_reminder(text)
    if ok2:
        session.metadata[FLOW_KEY] = {
            "stage": STAGE_NEED_DATE,
            "content": msg_content2,
            "hour": hour,
            "minute": minute,
            "retry_count": 0,
        }
        ctx.session_manager.save(session)
        if is_consulta_context(msg_content2):
            return REMINDER_ASK_DATE_CONSULTA.get(user_lang, REMINDER_ASK_DATE_CONSULTA["en"])
        return REMINDER_ASK_DATE_GENERIC.get(user_lang, REMINDER_ASK_DATE_GENERIC["en"])

    return None


# ---------------------------------------------------------------------------
# Confirmações (1=sim 2=não). Sem botões.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Handlers por comando (README: /lembrete, /list, /feito)
# ---------------------------------------------------------------------------

def _looks_like_reminder_nl(text: str) -> bool:
    """True se parece pedido de lembrete em linguagem natural (avisar/lembrar + tempo)."""
    if not text:
        return False
    t = text.strip().lower()
    if t.startswith("/"):
        return False
    
    # Import tardio para evitar circular dependancy
    from backend.reminder_keywords import ALL_REMINDER_KEYWORDS
    
    # Se contém keyword de lembrete E algo que pareça tempo
    has_kw = any(kw in t for kw in ALL_REMINDER_KEYWORDS)
    
    # Padrões de tempo: "hoje", "amanhã", "daqui a", "em 2 min", "as 10h", etc.
    time_ref = (
        "hoje" in t or "amanhã" in t or "amanha" in t or "às " in t or "as " in t
        or "dia " in t or "daqui" in t or " em " in t 
        or re.search(r"\d{1,2}\s*(min|h|seg|dia|mes|ano)", t, re.I) is not None
        or re.search(r"\d{1,2}\s*/\s*\d", t) is not None
        or re.search(r"\d{1,2}[:h]\d{2}", t, re.I) is not None
    )
    
    # Se for muito curto (ex: "Lembre-me"), não é suficiente sem tempo
    if len(t) < 7:
        return False
        
    return has_kw and time_ref


def _normalize_nl_to_command(content: str) -> str:
    """Reexport para uso neste módulo; lógica em backend.command_nl."""
    from backend.command_nl import normalize_nl_to_command
    return normalize_nl_to_command(content)


async def handle_lembrete(ctx: HandlerContext, content: str) -> str | None:
    """/lembrete [msg] [data/hora]. Ex: /lembrete reunião amanhã 14h. Aceita NL: 'avisar me hoje 10h'."""
    from backend.command_parser import parse
    from backend.guardrails import is_absurd_request, user_insisting_on_interval_rejection
    from backend.recurring_detector import maybe_ask_recurrence
    from backend.locale import LangCode, resolve_response_language
    from backend.user_store import get_user_language, get_user_timezone
    from backend.database import SessionLocal

    text = content.strip()
    # Se parecer pedido de remoção / cancelamento, ignorar e deixar para o Agente ou handler específico
    t_lower = text.lower()
    if any(kw in t_lower for kw in ["remov", "delet", "apag", "cancel", "para", "stop", "tirar"]):
        # A menos que seja um comando explícito /lembrete (mas mesmo assim o Agent é mais robusto para ID vs Nome)
        if not text.startswith("/"):
            return None

    if _looks_like_reminder_nl(text):
        text = "/lembrete " + text

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    tz_iana = "UTC"
    user_lang: LangCode = "pt-BR"
    try:
        db = SessionLocal()
        try:
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, ctx.phone_for_locale)
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz_iana)
            except Exception:
                from backend.timezone import phone_to_default_timezone
                tz_iana = phone_to_default_timezone(ctx.phone_for_locale or ctx.chat_id)
        finally:
            db.close()
    except Exception:
        pass
    if tz_iana == "UTC":
        from backend.timezone import DEFAULT_TZ_BY_LANG
        if user_lang in DEFAULT_TZ_BY_LANG:
            tz_iana = DEFAULT_TZ_BY_LANG[user_lang]

    intent = parse(text, tz_iana=tz_iana)
    if not intent or intent.get("type") != "lembrete":
        return None
    allow_relaxed = await user_insisting_on_interval_rejection(
        ctx.session_manager, ctx.channel, ctx.chat_id, content,
        ctx.scope_provider, ctx.scope_model or "",
    )
    if is_absurd_request(content, allow_relaxed=allow_relaxed):
        return is_absurd_request(content, allow_relaxed=allow_relaxed)
    if not ctx.cron_service or not ctx.cron_tool:
        return None
    msg_text = (intent.get("message") or "").strip()
    if not msg_text:
        return None
    in_sec = intent.get("in_seconds")
    every_sec = intent.get("every_seconds")
    cron_expr = intent.get("cron_expr")

    # Verificação rigorosa de tempo passado: se for > 60s no passado, rejeitar imediatamente.
    # O cron_tool também valida, mas aqui damos resposta directa sem tentar agendar.
    if in_sec is not None and in_sec < -60:
        from backend.locale import REMINDER_TIME_PAST_TODAY
        return REMINDER_TIME_PAST_TODAY.get(user_lang, REMINDER_TIME_PAST_TODAY["pt-BR"])
    start_date = intent.get("start_date")
    depends_on = intent.get("depends_on_job_id")
    date_in_past = intent.get("date_in_past")
    if date_in_past and in_sec is not None and in_sec > 0:
        from backend.confirmations import set_pending
        from backend.locale import REMINDER_DATE_PAST_ASK_NEXT_YEAR
        set_pending(
            ctx.channel,
            ctx.chat_id,
            "date_past_next_year",
            {
                "in_seconds": in_sec,
                "message": msg_text,
                "has_deadline": bool(intent.get("has_deadline")),
            },
        )
        return REMINDER_DATE_PAST_ASK_NEXT_YEAR.get(user_lang, REMINDER_DATE_PAST_ASK_NEXT_YEAR["pt-BR"])
    if not (in_sec or every_sec or cron_expr):
        # Encadeamento ("depois de X", "após Y") é tratado pelo LLM em linguagem natural
        msg_lower = (msg_text or "").lower()
        if "depois de" in msg_lower or " após " in msg_lower or "após " in msg_lower:
            return None
        # Encadeado sem tempo (legado): dispara quando o anterior estiver feito
        if depends_on:
            in_sec = 1
        else:
            # Sem tempo: se parecer recorrente, solicitar recorrência
            user_lang: LangCode = "pt-BR"
            try:
                db = SessionLocal()
                try:
                    user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
                    user_lang = resolve_response_language(user_lang, ctx.chat_id, ctx.phone_for_locale)
                finally:
                    db.close()
            except Exception:
                pass
            ask_msg = await maybe_ask_recurrence(
                content, user_lang, ctx.scope_provider, ctx.scope_model or "",
            )
            if ask_msg:
                return ask_msg
            return None
    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    result = await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        in_seconds=in_sec,
        every_seconds=every_sec,
        cron_expr=cron_expr,
        start_date=start_date,
        allow_relaxed_interval=allow_relaxed,
        depends_on_job_id=depends_on,
        has_deadline=bool(intent.get("has_deadline")),
    )
    return _append_tz_hint_if_needed(result, ctx.chat_id)


async def handle_list_or_events_ambiguous(ctx: HandlerContext, content: str) -> str | None:
    """Quando o utilizador diz 'tenho de X, Y' (2+ itens) sem 'muita coisa': pergunta se quer lista ou lembretes."""
    from backend.command_parser import parse
    from backend.confirmations import set_pending
    intent = parse(content)
    if not intent or intent.get("type") != "list_or_events_ambiguous":
        return None

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    items = intent.get("items") or []
    if len(items) < 2:
        return None
    set_pending(ctx.channel, ctx.chat_id, "list_or_events_choice", {"items": items})
    from backend.user_store import get_user_language
    from backend.database import SessionLocal
    from backend.locale import AMBIGUOUS_CHOICE_MSG
    lang = "pt-BR"
    try:
        db = SessionLocal()
        lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        db.close()
    except Exception:
        pass
    
    msg = AMBIGUOUS_CHOICE_MSG.get(lang, AMBIGUOUS_CHOICE_MSG["pt-BR"])
    return msg


async def handle_list(ctx: HandlerContext, content: str) -> str | None:
    """/list nome add item, /list filme|livro|musica item, ou /list [nome]."""
    from backend.command_parser import parse
    from backend.guardrails import is_absurd_request
    from loguru import logger
    intent = parse(content)
    if not intent or intent.get("type") not in ("list_add", "list_show"):
        return None

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    if not ctx.list_tool:
        logger.warning("handle_list: list_tool is None, chat_id=%s", (ctx.chat_id or "")[:24])
        return None
    logger.debug("handle_list: type=%s list_name=%s", intent.get("type"), intent.get("list_name"))
    if intent.get("type") == "list_add":
        list_name = intent.get("list_name", "")
        items = intent.get("items")
        item_text = intent.get("item", "")
        if items:
            for it in items:
                if list_name in ("filme", "livro", "musica", "receita") and is_absurd_request(it):
                    r = is_absurd_request(it)
                    if r:
                        return r
        elif list_name in ("filme", "livro", "musica", "receita") and is_absurd_request(item_text):
            return is_absurd_request(item_text)
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    if intent.get("type") == "list_add":
        items_to_add = intent.get("items") or ([intent.get("item")] if intent.get("item") else [])
        if not items_to_add:
            return None
        list_name = intent.get("list_name", "")
        results = []
        for it in items_to_add:
            r = await ctx.list_tool.execute(
                action="add",
                list_name=list_name,
                item_text=it,
            )
            results.append(r)
        return "\n".join(results) if len(results) > 1 else (results[0] if results else None)
    return await ctx.list_tool.execute(
        action="list",
        list_name=intent.get("list_name") or "",
    )


# ---------------------------------------------------------------------------
# Alias: /add [lista] [item] (default lista=mercado). Feito: por áudio, texto ou emoji.
# ---------------------------------------------------------------------------

async def handle_add(ctx: HandlerContext, content: str) -> str | None:
    """/add [lista] [item]. Default lista=mercado. Aceita NL: adicione X, adiciona X."""
    content = _normalize_nl_to_command(content)
    
    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    m = re.match(r"^/add\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    rest = m.group(1).strip()
    parts = rest.split(None, 1)
    if len(parts) == 1:
        list_name, item = "mercado", parts[0]
    else:
        list_name, item = parts[0], parts[1]
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    return await ctx.list_tool.execute(action="add", list_name=list_name, item_text=item)


async def handle_feito(ctx: HandlerContext, content: str) -> str | None:
    """/feito [lista] [id]. Aceita NL: concluído, feito, pronto, ok."""
    from backend.command_parser import parse
    intent = parse(content)
    if not intent or intent.get("type") != "feito":
        return None
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    return await ctx.list_tool.execute(
        action="feito",
        list_name=intent.get("list_name") or "",
        item_id=intent.get("item_id"),
    )


async def handle_remove(ctx: HandlerContext, content: str) -> str | None:
    """/remove [lista] [id]. Aceita NL: remover, apagar, deletar, tirar."""
    from backend.command_parser import parse
    intent = parse(content)
    if not intent or intent.get("type") != "remove":
        return None
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    return await ctx.list_tool.execute(
        action="remove",
        list_name=intent.get("list_name") or "",
        item_id=intent.get("item_id"),
    )


async def handle_hora_data(ctx: HandlerContext, content: str) -> str | None:
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
        # data
        from backend.locale import resolve_response_language
        lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
        # Formato d/m/y para todos menos EN
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


# ---------------------------------------------------------------------------
# /start, /recorrente, /pendente, /stop (tz/lang/quiet/reset em settings_handlers)
# ---------------------------------------------------------------------------

async def handle_start(ctx: HandlerContext, content: str) -> str | None:
    """/start: opt-in, setup timezone/idioma. Aceita NL: começar, início, iniciar."""
    content = _normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/start"):
        return None
    return (
        "👋 Olá! Sou o Zappelin: lembretes, listas e eventos.\n\n"
        "📌 Comandos: /lembrete, /list (filme, livro, musica, receita, notas, compras…).\n"
        "🌍 Timezone: /tz Cidade  |  Idioma: /lang pt-pt ou pt-br ou es ou en.\n\n"
        "Digite /help para ver tudo — ou escreve/envia áudio para conversar. 😊"
    )


async def handle_help(ctx: HandlerContext, content: str) -> str | list[str] | None:
    """/help, /ajuda: lista completa de comandos. Aceita NL: ajuda, comandos, o que você faz. Devolve [texto principal, comandos slash] para enviar em duas mensagens."""
    content = _normalize_nl_to_command(content)
    c = content.strip().lower()
    if not (c.startswith("/help") or c.startswith("/ajuda") or c.startswith("/ayuda")):
        return None
    from backend.locale import build_help, build_help_commands_list, resolve_response_language

    user_lang = "pt-BR"
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, ctx.phone_for_locale)
        finally:
            db.close()
    except Exception:
        # Fallback para pt-BR se a base de dados falhar (ex.: stress test sem DB)
        pass

    main = build_help(user_lang)
    commands_msg = build_help_commands_list(user_lang)
    return [main, commands_msg]


async def handle_recorrente(ctx: HandlerContext, content: str) -> str | None:
    """/recorrente [msg] [freq]. Aceita NL: lembrete recorrente X, todo dia X."""
    content = _normalize_nl_to_command(content)
    from backend.command_parser import parse
    from backend.user_store import get_user_timezone
    from backend.database import SessionLocal
    m = re.match(r"^/recorrente\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    rest = m.group(1).strip()
    tz_iana = "UTC"
    try:
        db = SessionLocal()
        try:
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
        finally:
            db.close()
    except Exception:
        pass
    intent = parse("/lembrete " + rest, tz_iana=tz_iana)
    if not intent or intent.get("type") != "lembrete":
        return None
    if not ctx.cron_service or not ctx.cron_tool:
        return None
    msg_text = (intent.get("message") or "").strip() or rest
    every_sec = intent.get("every_seconds")
    cron_expr = intent.get("cron_expr")
    start_date = intent.get("start_date")
    if not (every_sec or cron_expr):
        return "📅 Usa algo como: /recorrente academia segunda 7h  ou  /recorrente beber água a cada 1 hora"
    depends_on = intent.get("depends_on_job_id")
    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    result = await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        every_seconds=every_sec,
        cron_expr=cron_expr,
        start_date=start_date,
        depends_on_job_id=depends_on,
    )
    return _append_tz_hint_if_needed(result, ctx.chat_id)


async def handle_pendente(ctx: HandlerContext, content: str) -> str | None:
    """/pendente: tudo aberto. Aceita NL: pendente, pendentes, tarefas pendentes."""
    content = _normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/pendente"):
        return None
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    return await ctx.list_tool.execute(action="list", list_name="")


async def handle_stop(ctx: HandlerContext, content: str) -> str | None:
    """/stop: opt-out. Aceita NL: parar, pausar, stop."""
    content = _normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/stop"):
        return None
    return _reply_confirm_prompt(
        "🔕 Quer pausar as mensagens? Vais deixar de receber lembretes e notificações."
    )


# ---------------------------------------------------------------------------
# Pedido de lembrete sem tempo (natural language) → solicitar recorrência se recorrente
# ---------------------------------------------------------------------------

# Padrões que NUNCA são pedido de lembrete — reduz falsos positivos em handle_recurring_prompt
_NOT_REMINDER_PATTERNS = (
    # Localização / geografia
    r"sabe\s+onde", r"onde\s+fica", r"onde\s+est[aá]", r"where\s+is",
    r"qual\s+(é|e)\s+(a\s+)?capital", r"como\s+chego", r"como\s+chegar",
    r"localiza[cç][aã]o\s+de", r"endere[cç]o", r"coordinates",
    # Pedidos de MOSTRAR/VER/ADD lista (nunca lembrete)
    r"mostr(e|ar)\s+(a\s+)?lista", r"ver\s+(a\s+)?lista", r"ver\s+minha\s+lista",
    r"qual\s+(é|e)\s+(a\s+)?minha\s+lista", r"qual\s+(é|e)\s+sua\s+lista",
    r"lista\s+de\s+\w+", r"minha\s+lista\s+(de\s+)?\w*", r"listar\s+\w+",
    r"^(lista|mercado|compras|pendentes)\s*$",
    r"add\s+lista\b", r"add\s+list\b", r"adicione?\s+(à|a)\s+lista",
    r"lista\s+(filmes?|livros?|m[uú]sicas?|receitas?)\b",
    # Add/put/include em lista (PT, EN, ES)
    r"(?:adiciona|adicionar|coloca|coloque|p[oô]e|põe|inclui|incluir|p[oô]r)\s+",
    r"(?:put|add|include|append)\s+.*\s+(?:to|on|in)\s+(?:the\s+)?(?:list|shopping)",
    r"(?:anota|anotar|regista|registar|marca|marcar)\s+",
    r"(?:anotar|registar|marcar)\s+.*\s+(?:para\s+)?(?:ver|comprar|ler|ouvir)",
    r"lembra[- ]?me\s+de\s+comprar", r"n[aã]o\s+esque[cç]as?\s+de\s+comprar",
    r"(?:lembrar|lembre)[- ]?me\s+de\s+comprar", r"lembra\s+de\s+comprar",
    r"para\s+comprar\s*:", r"coisas?\s+para\s+comprar", r"falta\s+comprar\b",
    r"(?:filme|livro|m[uú]sica)\s+para\s+(?:ver|ler|ouvir)", r"quero\s+ver\s+(?:o\s+)?filme",
    r"quero\s+ler\s+(?:o\s+)?livro", r"(?:filme|livro)\s+(?:para\s+)?(?:ver|ler)\s*:",
    r"ingredientes?\s+para\s+", r"o\s+que\s+preciso\s+para\s+fazer\s+",
    r"vou\s+precisar\s+de\s+.*\s+(?:para\s+a\s+)?receita",
    r"(?:preciso|quero)\s+(?:de\s+)?(?:comprar|anotar|adicionar)\b",
    # Receita/ingredientes (sempre excluir — handle_recipe ou LLM)
    r"receita\s+(?:de|da)\s+", r"receitas?\s+\w+", r"^receita\s+\w+",
    # Follow-ups sobre lista/receita (não são pedido de lembrete — vão ao LLM com contexto)
    r"cad[eê]\s+(a\s+)?(lista|receita|ingredientes)",
    r"onde\s+(est[aá]|est[aã]o)\s+(a\s+)?(lista|receita|ingredientes)",
    r"e\s+(a\s+)?(lista|receita|os?\s+ingredientes)",
    r"^(cad[eê]|cad[eê]\s+a)\b", r"fa[cç]a\s+uma\s+lista", r"fazer\s+uma\s+lista",
    # Compras = lista (não lembrete recorrente)
    r"preciso\s+comprar", r"quero\s+comprar", r"comprar\s+(leite|pão|ovo|arroz)",
    r"adicion[eia](?:r)?\s+", r"(?:a|à|nas?)\s+listas?\b",  # "adicione X a listas"
    r"preciso\s+(mercado|compras)\b", r"quero\s+(mercado|compras)\b",
    r"lista\s+(do\s+)?mercado", r"lista\s+mercado", r"itens?\s+(do\s+)?mercado",
    # Perguntas gerais (não pedido de lembrete)
    r"^(o\s+que\s+é|oq\s+é|o\s+que\s+e)\b", r"qual\s+(é|e)\s+o\s+significado",
    r"como\s+(fazer|usar|funciona)", r"quanto\s+custa", r"quanto\s+(é|e)\s+",
    r"^(quem|como|porque|por\s+que)\b",
    # Versículo / texto sagrado (já tratado antes)
    r"vers[ií]culo", r"b[ií]blia", r"passagem\s+b[ií]blica",
    # Saudações / despedidas
    r"^(oi|ol[aá]|ola|hey|hi)\s*$", r"^(tchau|bye|at[eé])\s*$",
    r"^(obrigad[oa]|obg|valeu|thx)\s*$",
    # Números / links
    r"^\d{1,4}\s*$", r"^https?://", r"^www\.", r"\.com\b", r"\.pt\b",
    # Pedido de idioma / instrução (não lembrete)
    r"fala[r]?\s+em\s+portugu[eê]s", r"portugu[eê]s\s+(?:do\s+)?(?:brasil|br)",
    r"portugu[eê]s\s+(?:de\s+)?portugal", r"continuar\s+em\s+",
    r"quero\s+fala[r]?\s+em\s+", r"(?:speak|hablar)\s+(?:in\s+)?(?:portuguese|spanish|english)",
    # Outros
    r"^(sim|n[aã]o|não|nope)\s*$",  # respostas curtas
    r"^(status|ajuda|help)\s*$", r"^/",
)


async def handle_recurring_prompt(ctx: HandlerContext, content: str) -> str | None:
    """Quando o usuário pede lembrete em linguagem natural sem data (ex: 'lembrar de tomar remédio'), e parece recorrente, pergunta a frequência."""
    import re
    from backend.recurring_detector import maybe_ask_recurrence
    from backend.scope_filter import is_in_scope_fast
    from backend.user_store import get_user_language
    from backend.database import SessionLocal
    from backend.locale import LangCode, resolve_response_language
    from backend.integrations.sacred_text import _is_sacred_text_intent

    if _is_sacred_text_intent(content or ""):
        return None
    t = (content or "").strip().lower()
    if not t:
        return None
    if not is_in_scope_fast(t):
        return None
    for pat in _NOT_REMINDER_PATTERNS:
        if re.search(pat, t):
            return None
    user_lang: LangCode = "pt-BR"
    try:
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, ctx.phone_for_locale)
        finally:
            db.close()
    except Exception:
        pass
    return await maybe_ask_recurrence(
        content, user_lang, ctx.scope_provider, ctx.scope_model or "",
    )


# ---------------------------------------------------------------------------
# Evento recorrente agendado (academia segunda 19h, aulas terça 10h)
# ---------------------------------------------------------------------------

async def handle_recurring_event(ctx: HandlerContext, content: str) -> str | None:
    """
    Quando o utilizador indica evento recorrente com horário (academia segunda e quarta 19h):
    1. Detecta, diz de forma simpática que é recorrente, pede confirmação
    2. Confirma → pergunta até quando (indefinido, fim da semana, fim do mês)
    3. Registra com cron_expr (e opcional not_after_ms)
    """
    import re
    from backend.recurring_event_flow import (
        FLOW_KEY,
        STAGE_NEED_CONFIRM,
        STAGE_NEED_END_DATE,
        is_scheduled_recurring_event,
        parse_recurring_schedule,
        format_schedule_for_display,
        parse_end_date_response,
        looks_like_confirm_yes,
        looks_like_confirm_no,
        compute_end_date_ms,
    )
    from backend.recurring_event_flow import MAX_RETRIES_END_DATE
    from backend.locale import (
        LangCode,
        RECURRING_EVENT_CONFIRM,
        RECURRING_ASK_END_DATE,
        RECURRING_ASK_END_DATE_AGAIN,
        RECURRING_REGISTERED,
        RECURRING_REGISTERED_UNTIL,
    )
    from backend.user_store import get_user_language, get_user_timezone
    from backend.database import SessionLocal
    from backend.locale import resolve_response_language

    if not ctx.session_manager or not ctx.cron_tool or not content or not content.strip():
        return None

    text = content.strip()
    if re.match(r"^/lembrete\s+", text, re.I):
        text = re.sub(r"^/lembrete\s+", "", text, flags=re.I).strip()

    # --- Cancelar fluxo se o usuário pedir ---
    t_clean = content.strip().lower()
    if t_clean in ("esc", "cancel", "cancelar", "sair", "stop", "para", "parar", "nvm"):
        session_key = f"{ctx.channel}:{ctx.chat_id}"
        session = ctx.session_manager.get_or_create(session_key)
        if session.metadata.get(FLOW_KEY):
            session.metadata.pop(FLOW_KEY, None)
            ctx.session_manager.save(session)
            return "Ok, cancelado. 👍" if user_lang.startswith("pt") else ("Vale, cancelado. 👍" if user_lang == "es" else "Okay, cancelled. 👍")

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    flow = session.metadata.get(FLOW_KEY)

    user_lang: LangCode = "pt-BR"
    tz_iana = "UTC"
    try:
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, ctx.phone_for_locale)
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz_iana)
            except Exception:
                from backend.timezone import phone_to_default_timezone
                tz_iana = phone_to_default_timezone(ctx.phone_for_locale or ctx.chat_id)
        finally:
            db.close()
    except Exception:
        pass

    # --- Estamos no fluxo ---
    if flow and isinstance(flow, dict):
        stage = flow.get("stage")
        event = (flow.get("event") or "").strip()
        cron_expr = (flow.get("cron_expr") or "").strip()
        schedule_display = format_schedule_for_display(cron_expr, user_lang)

        if stage == STAGE_NEED_CONFIRM:
            if looks_like_confirm_no(text):
                session.metadata.pop(FLOW_KEY, None)
                ctx.session_manager.save(session)
                return None
            if looks_like_confirm_yes(text):
                session.metadata[FLOW_KEY] = {
                    **flow,
                    "stage": STAGE_NEED_END_DATE,
                }
                ctx.session_manager.save(session)
                return RECURRING_ASK_END_DATE.get(user_lang, RECURRING_ASK_END_DATE["en"])
            return None

        if stage == STAGE_NEED_END_DATE:
            end_type = parse_end_date_response(text)
            if not end_type:
                retry = flow.get("retry_count", 0) + 1
                if retry >= MAX_RETRIES_END_DATE:
                    session.metadata.pop(FLOW_KEY, None)
                    ctx.session_manager.save(session)
                    return None
                flow["retry_count"] = retry
                session.metadata[FLOW_KEY] = flow
                ctx.session_manager.save(session)
                return RECURRING_ASK_END_DATE_AGAIN.get(user_lang, RECURRING_ASK_END_DATE_AGAIN["en"])

            session.metadata.pop(FLOW_KEY, None)
            ctx.session_manager.save(session)

            not_after_ms = None
            end_display = ""
            if end_type != "indefinido":
                not_after_ms = compute_end_date_ms(end_type, tz_iana)
                from datetime import datetime
                from zoneinfo import ZoneInfo
                if not_after_ms:
                    end_display = datetime.fromtimestamp(not_after_ms / 1000, tz=ZoneInfo(tz_iana)).strftime("%d/%m/%Y")

            ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
            end_param = not_after_ms if not_after_ms else None
            result = await ctx.cron_tool.execute(
                action="add",
                message=event,
                cron_expr=cron_expr,
                end_date=end_param,
            )
            if result and "Error" not in result:
                if end_display:
                    out = RECURRING_REGISTERED_UNTIL.get(user_lang, RECURRING_REGISTERED_UNTIL["en"]).format(
                        event=event, schedule=schedule_display, end=end_display
                    )
                else:
                    out = RECURRING_REGISTERED.get(user_lang, RECURRING_REGISTERED["en"]).format(
                        event=event, schedule=schedule_display
                    )
                return _append_tz_hint_if_needed(out, ctx.chat_id, ctx.phone_for_locale)
            return result

    # --- Novo pedido: detectar evento recorrente com horário ---
    parsed = parse_recurring_schedule(text)
    if parsed and is_scheduled_recurring_event(text):
        event_content, cron_expr, hour, minute = parsed
        schedule_display = format_schedule_for_display(cron_expr, user_lang)

        session.metadata[FLOW_KEY] = {
            "stage": STAGE_NEED_CONFIRM,
            "event": event_content,
            "cron_expr": cron_expr,
        }
        ctx.session_manager.save(session)

        return RECURRING_EVENT_CONFIRM.get(user_lang, RECURRING_EVENT_CONFIRM["en"]).format(
            event=event_content,
            schedule=schedule_display,
        )

        return None


# Route e HANDLERS em backend.router (agent loop importa route de router)
