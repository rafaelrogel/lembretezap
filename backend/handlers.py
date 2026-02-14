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
    Se a mensagem for curta e parecer confirmação (sim, quero, ok) E a última do assistente
    foi uma oferta de lembrete, usa Mimo para extrair os params e executa cron add.
    """
    from backend.pending_confirmation import looks_like_confirmation, try_extract_pending_cron

    if not looks_like_confirmation(content):
        return None
    if not ctx.cron_tool or not ctx.session_manager or not ctx.scope_provider or not ctx.scope_model:
        return None

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    history = session.get_history(max_messages=10)
    if len(history) < 2:
        return None

    params = await try_extract_pending_cron(
        ctx.scope_provider,
        ctx.scope_model,
        history,
        content,
    )
    if not params:
        return None

    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
    msg_text = (params.get("message") or "").strip()
    if not msg_text:
        return None
    every = params.get("every_seconds")
    in_sec = params.get("in_seconds")
    result = await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        every_seconds=every,
        in_seconds=in_sec,
    )
    return result


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
    from backend.locale import LangCode
    from backend.user_store import get_user_language
    from backend.database import SessionLocal

    intent = parse(content)
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
        # Encadeado sem tempo: dispara imediatamente quando o anterior estiver feito
        if depends_on:
            in_sec = 1
        else:
            # Sem tempo: se parecer recorrente, solicitar recorrência
            user_lang: LangCode = "pt-BR"
            try:
                db = SessionLocal()
                try:
                    user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
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
        item_text = intent.get("item", "")
        if list_name in ("filme", "livro", "musica", "receita") and is_absurd_request(item_text):
            return is_absurd_request(item_text)
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    if intent.get("type") == "list_add":
        return await ctx.list_tool.execute(
            action="add",
            list_name=intent.get("list_name", ""),
            item_text=intent.get("item", ""),
        )
    return await ctx.list_tool.execute(
        action="list",
        list_name=intent.get("list_name") or "",
    )


async def handle_feito(ctx: HandlerContext, content: str) -> str | None:
    """/feito nome id. Ex: /feito mercado 1 – marca feito e remove."""
    from backend.command_parser import parse
    intent = parse(content)
    if not intent or intent.get("type") != "feito":
        return None
    if not ctx.list_tool:
        return None
    list_name = intent.get("list_name")
    item_id = intent.get("item_id")
    if item_id is None:
        return "Use: /feito nome_da_lista id (ex: /feito mercado 1) ou /feito id (ex: /feito 1)"
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.list_tool.execute(action="feito", list_name=list_name, item_id=item_id)


# ---------------------------------------------------------------------------
# Aliases: /add [lista] [item] (default lista=mercado), /done nome n
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


async def handle_done(ctx: HandlerContext, content: str) -> str | None:
    """/done nome n. Ex: /done mercado 1 – remove item."""
    import re
    m = re.match(r"^/done\s+(\S+)\s+(\d+)\s*$", content.strip(), re.I)
    if not m:
        return None
    list_name, item_id = m.group(1).strip(), int(m.group(2))
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.list_tool.execute(action="feito", list_name=list_name, item_id=item_id)


# ---------------------------------------------------------------------------
# /start, /recorrente, /pendente, /stop (tz/lang/quiet/reset em settings_handlers)
# ---------------------------------------------------------------------------

async def handle_start(ctx: HandlerContext, content: str) -> str | None:
    """/start: opt-in, setup timezone/idioma via texto."""
    if not content.strip().lower().startswith("/start"):
        return None
    return (
        "👋 Olá! Sou o Zapista: lembretes, listas e eventos.\n\n"
        "📌 Comandos: /lembrete, /list (filme, livro, musica, receita, compras…), /feito.\n"
        "🌍 Timezone: /tz Cidade  |  Idioma: /lang pt-pt ou pt-br ou es ou en.\n\n"
        "Digite /help para ver tudo. 😊"
    )


async def handle_help(ctx: HandlerContext, content: str) -> str | None:
    """/help: lista de comandos e como usar o assistente."""
    if not content.strip().lower().startswith("/help"):
        return None
    return (
        "📋 **Comandos disponíveis:**\n"
        "• /lembrete — agendar (ex.: amanhã 9h; em 30 min; depois de PIX = encadear)\n"
        "• /list — listas: /list mercado add leite  ou  /list filme Matrix  /list livro 1984  /list musica Nome  /list receita Bolo\n"
        "• /feito — marcar item como feito: /feito mercado 1  ou  /feito 1\n"
        "• /hoje, /semana, /mes — ver o que tens hoje, esta semana ou calendário do mês\n"
        "• /timeline — histórico cronológico (lembretes, tarefas, eventos)\n"
        "• /stats — estatísticas (tarefas feitas, lembretes); /stats dia ou /stats semana\n"
        "• /produtividade — relatório semanal/mensal; /produtividade mes para ver por mês\n"
        "• /revisao — resumo da semana (tarefas, lembretes, eventos)\n"
        "• /habito add Nome, /habito check Nome, /habito hoje — hábitos diários\n"
        "• /meta add Nome até DD/MM — metas com prazo; /metas para listar\n"
        "• /nota texto — notas rápidas; /notas para ver\n"
        "• /projeto add Nome — projetos; /projeto Nome add item — agrupar tarefas\n"
        "• /template add Nome item1, item2 — modelos; /template Nome usar\n"
        "• /save [desc] ou /bookmark — guardar com tags e categoria (IA)\n"
        "• /find \"aquela receita\" — busca semântica nos bookmarks\n"
        "• /limpeza — tarefas de limpeza (weekly/bi-weekly) com rotação para flatmates\n"
        "• Cripto — pergunta «bitcoin», «cotação» e recebe cotações (BTC, ETH, USDT, XRP, BNB)\n"
        "• Bíblia/Alcorão — pede «passagem da bíblia» ou «versículo do alcorão» (aleatório ou específico)\n"
        "• /tz Cidade — definir fuso (ex.: /tz Lisboa)\n"
        "• /lang pt-pt ou pt-br — idioma\n"
        "• /reset — refazer cadastro (nome, cidade)\n"
        "• /quiet 22:00-08:00 — horário silencioso\n\n"
        "Ou simplesmente conversa comigo: diz o que precisas e eu ajudo a organizar. 😊"
    )


async def handle_recorrente(ctx: HandlerContext, content: str) -> str | None:
    """/recorrente [msg] [freq]. Ex: /recorrente academia seg 7h."""
    from backend.command_parser import parse
    import re
    m = re.match(r"^/recorrente\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    rest = m.group(1).strip()
    intent = parse("/lembrete " + rest)
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

# Padrões que NUNCA são pedido de lembrete (localização, conhecimento geral, etc.)
_NOT_REMINDER_PATTERNS = (
    r"sabe\s+onde", r"onde\s+fica", r"onde\s+est[aá]", r"where\s+is",
    r"qual\s+(é|e)\s+(a\s+)?capital", r"como\s+chego", r"como\s+chegar",
    r"localiza[cç][aã]o\s+de", r"endere[cç]o", r"coordinates",
)


async def handle_recurring_prompt(ctx: HandlerContext, content: str) -> str | None:
    """Quando o usuário pede lembrete em linguagem natural sem data (ex: 'lembrar de tomar remédio'), e parece recorrente, pergunta a frequência."""
    import re
    from backend.recurring_detector import maybe_ask_recurrence
    from backend.scope_filter import is_in_scope_fast
    from backend.user_store import get_user_language
    from backend.database import SessionLocal
    from backend.locale import LangCode
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
        finally:
            db.close()
    except Exception:
        pass
    return await maybe_ask_recurrence(
        content, user_lang, ctx.scope_provider, ctx.scope_model or "",
    )


# Route e HANDLERS em backend.router (agent loop importa route de router)
