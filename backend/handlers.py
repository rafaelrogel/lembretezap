"""Handlers de comandos EXATAMENTE como no README: /lembrete, /list nome add item, /feito nome id.

- Sem botões interativos (sem Business API): confirmações com texto "1=sim 2=não".
- TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']).
- Persistência em SQLite (user_phone → listas/lembretes) via backend.models_db e cron.
- Baileys via gateway: resposta em texto (client.sendMessage(jid, {text: msg})).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from zapista.agent.tools.cron import CronTool
    from zapista.agent.tools.list_tool import ListTool
    from zapista.agent.tools.event_tool import EventTool
    from zapista.cron.service import CronService

from backend.handler_context import HandlerContext, _reply_confirm_prompt

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

    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
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
    return result


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
    )
    from backend.user_store import get_user_language, get_user_timezone
    from backend.database import SessionLocal
    from backend.locale import resolve_response_language

    if not ctx.session_manager or not ctx.cron_tool or not content or not content.strip():
        return None

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
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, None)
            tz_iana = get_user_timezone(db, ctx.chat_id) or "UTC"
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz_iana)
            except Exception:
                from backend.timezone import phone_to_default_timezone
                tz_iana = phone_to_default_timezone(ctx.chat_id)
        finally:
            db.close()
    except Exception:
        pass

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
            if looks_like_advance_preference_no(text):
                # Só na hora → criar 1 lembrete
                in_sec = flow.get("in_seconds")
                if in_sec and in_sec > 0:
                    session.metadata.pop(FLOW_KEY, None)
                    ctx.session_manager.save(session)
                    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
                    result = await ctx.cron_tool.execute(
                        action="add",
                        message=msg_content,
                        in_seconds=in_sec,
                    )
                    return result

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
                    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
                    # 2 lembretes: aviso (in_sec - advance_sec) e na hora (in_sec)
                    advance_in_sec = max(60, in_sec - advance_sec)
                    r1 = await ctx.cron_tool.execute(
                        action="add",
                        message=f"(Aviso) {msg_content}",
                        in_seconds=advance_in_sec,
                    )
                    r2 = await ctx.cron_tool.execute(
                        action="add",
                        message=msg_content,
                        in_seconds=in_sec,
                    )
                    return f"{r1}\n\n{r2}" if r1 and r2 else (r1 or r2)

            q = REMINDER_ASK_ADVANCE_PREFERENCE.get(user_lang, REMINDER_ASK_ADVANCE_PREFERENCE["en"])
            return _retry_or_fail(flow, q)

        elif stage == STAGE_NEED_ADVANCE_AMOUNT:
            advance_sec = parse_advance_seconds(text)
            if advance_sec:
                in_sec = flow.get("in_seconds")
                if in_sec and in_sec > 0:
                    session.metadata.pop(FLOW_KEY, None)
                    ctx.session_manager.save(session)
                    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
                    advance_in_sec = max(60, in_sec - advance_sec)
                    r1 = await ctx.cron_tool.execute(
                        action="add",
                        message=f"(Aviso) {msg_content}",
                        in_seconds=advance_in_sec,
                    )
                    r2 = await ctx.cron_tool.execute(
                        action="add",
                        message=msg_content,
                        in_seconds=in_sec,
                    )
                    return f"{r1}\n\n{r2}" if r1 and r2 else (r1 or r2)

            q = REMINDER_ASK_ADVANCE_AMOUNT.get(user_lang, REMINDER_ASK_ADVANCE_AMOUNT["en"])
            return _retry_or_fail(flow, q)

        # Fallback: resposta inválida em stage desconhecido
        return None

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

async def handle_lembrete(ctx: HandlerContext, content: str) -> str | None:
    """/lembrete [msg] [data/hora]. Ex: /lembrete reunião amanhã 14h."""
    from backend.command_parser import parse
    from backend.guardrails import is_absurd_request, user_insisting_on_interval_rejection
    from backend.recurring_detector import maybe_ask_recurrence
    from backend.locale import LangCode, resolve_response_language
    from backend.user_store import get_user_language, get_user_timezone
    from backend.database import SessionLocal

    tz_iana = "UTC"
    try:
        db = SessionLocal()
        try:
            tz_iana = get_user_timezone(db, ctx.chat_id) or "UTC"
        finally:
            db.close()
    except Exception:
        pass
    intent = parse(content, tz_iana=tz_iana)
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
    start_date = intent.get("start_date")
    depends_on = intent.get("depends_on_job_id")
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
                    user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                    user_lang = resolve_response_language(user_lang, ctx.chat_id, None)
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
    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.cron_tool.execute(
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


async def handle_list_or_events_ambiguous(ctx: HandlerContext, content: str) -> str | None:
    """Quando o utilizador diz 'tenho de X, Y' (2+ itens) sem 'muita coisa': pergunta se quer lista ou lembretes."""
    from backend.command_parser import parse
    from backend.confirmations import set_pending
    intent = parse(content)
    if not intent or intent.get("type") != "list_or_events_ambiguous":
        return None
    items = intent.get("items") or []
    if len(items) < 2:
        return None
    set_pending(ctx.channel, ctx.chat_id, "list_or_events_choice", {"items": items})
    return (
        "Queres que eu crie uma *lista de afazeres* (to-do) com estes itens ou prefires registar cada um como *lembrete* com horário? "
        "Também posso fazer *os dois*. Responde: *lista*, *lembretes* ou *os dois*."
    )


async def handle_list(ctx: HandlerContext, content: str) -> str | None:
    """/list nome add item, /list filme|livro|musica|receita item, ou /list [nome]. Filme/livro/musica/receita são listas dentro de /list."""
    from backend.command_parser import parse
    from backend.guardrails import is_absurd_request
    intent = parse(content)
    if not intent or intent.get("type") not in ("list_add", "list_show"):
        return None
    if not ctx.list_tool:
        return None
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
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
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
    """/add [lista] [item]. Default lista=mercado. UX: 'adicione pão' → LLM fallback."""
    import re
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
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.list_tool.execute(action="add", list_name=list_name, item_text=item)


# ---------------------------------------------------------------------------
# /start, /recorrente, /pendente, /stop (tz/lang/quiet/reset em settings_handlers)
# ---------------------------------------------------------------------------

async def handle_start(ctx: HandlerContext, content: str) -> str | None:
    """/start: opt-in, setup timezone/idioma via texto."""
    if not content.strip().lower().startswith("/start"):
        return None
    return (
        "👋 Olá! Sou o Zapista: lembretes, listas e eventos.\n\n"
        "📌 Comandos: /lembrete, /list (filme, livro, musica, receita, notas, compras…).\n"
        "🌍 Timezone: /tz Cidade  |  Idioma: /lang pt-pt ou pt-br ou es ou en.\n\n"
        "Digite /help para ver tudo — ou escreve/envia áudio para conversar. 😊"
    )


async def handle_help(ctx: HandlerContext, content: str) -> str | None:
    """/help: lista de comandos e como usar o assistente."""
    if not content.strip().lower().startswith("/help"):
        return None
    return (
        "*Comandos*\n"
        "• /lembrete — agendar (ex.: amanhã 9h; em 30 min)\n"
        "• /list — listas (compras, receitas, livros, músicas, notas, sites, coisas a fazer). Ex.: /list mercado add leite\n"
        "• /hoje, /semana — ver o que tens hoje ou esta semana\n"
        "• /timeline — histórico (lembretes, tarefas, eventos)\n"
        "• /stats — estatísticas; /stats dia ou /stats semana\n"
        "• /resumo — resumo da semana\n"
        "• /recorrente — lembretes recorrentes (ex.: /recorrente beber água todo dia 8h)\n"
        "• /meta add Nome até DD/MM — metas com prazo; /metas para listar\n"
        "• /pomodoro — timer 25 min foco; /pomodoro stop para cancelar\n\n"
        "*Configuração*\n"
        "• /tz Cidade — definir fuso (ex.: /tz Lisboa)\n"
        "• /lang — idioma: pt-pt, pt-br, es, en\n"
        "• /reset — refazer cadastro (nome, cidade)\n"
        "• /quiet 22:00-08:00 — horário silencioso\n\n"
        "*Dicas*\n"
        '• Marcar item como feito: podes dizer por áudio ("pronto", "já fiz"), escrever texto ou usar emoji ("✓", "👍") — não precisas de comando.\n'
        '• Conversa por mensagem ou áudio; se quiseres resposta em áudio, pede "responde em áudio", "manda áudio" ou "fala comigo". 😊'
    )


async def handle_recorrente(ctx: HandlerContext, content: str) -> str | None:
    """/recorrente [msg] [freq]. Ex: /recorrente academia seg 7h."""
    from backend.command_parser import parse
    from backend.user_store import get_user_timezone
    from backend.database import SessionLocal
    import re
    m = re.match(r"^/recorrente\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    rest = m.group(1).strip()
    tz_iana = "UTC"
    try:
        db = SessionLocal()
        try:
            tz_iana = get_user_timezone(db, ctx.chat_id) or "UTC"
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
    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        every_seconds=every_sec,
        cron_expr=cron_expr,
        start_date=start_date,
        depends_on_job_id=depends_on,
    )


async def handle_pendente(ctx: HandlerContext, content: str) -> str | None:
    """/pendente: tudo aberto (listas com itens não feitos)."""
    if not content.strip().lower().startswith("/pendente"):
        return None
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.list_tool.execute(action="list", list_name="")


async def handle_stop(ctx: HandlerContext, content: str) -> str | None:
    """/stop: opt-out."""
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
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, None)
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

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    flow = session.metadata.get(FLOW_KEY)

    user_lang: LangCode = "pt-BR"
    tz_iana = "UTC"
    try:
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
            user_lang = resolve_response_language(user_lang, ctx.chat_id, None)
            tz_iana = get_user_timezone(db, ctx.chat_id) or "UTC"
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz_iana)
            except Exception:
                from backend.timezone import phone_to_default_timezone
                tz_iana = phone_to_default_timezone(ctx.chat_id)
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

            ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
            end_param = not_after_ms if not_after_ms else None
            result = await ctx.cron_tool.execute(
                action="add",
                message=event,
                cron_expr=cron_expr,
                end_date=end_param,
            )
            if result and "Error" not in result:
                if end_display:
                    return RECURRING_REGISTERED_UNTIL.get(user_lang, RECURRING_REGISTERED_UNTIL["en"]).format(
                        event=event, schedule=schedule_display, end=end_display
                    )
                return RECURRING_REGISTERED.get(user_lang, RECURRING_REGISTERED["en"]).format(
                    event=event, schedule=schedule_display
                )
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
