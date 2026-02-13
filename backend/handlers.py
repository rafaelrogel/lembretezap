"""Handlers de comandos EXATAMENTE como no README: /lembrete, /list nome add item, /feito nome id.

- Sem botões interativos (sem Business API): confirmações com texto "1=sim 2=não".
- TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']).
- Persistência em SQLite (user_phone → listas/lembretes) via backend.models_db e cron.
- Baileys via gateway: resposta em texto (client.sendMessage(jid, {text: msg})).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.agent.tools.cron import CronTool
    from nanobot.agent.tools.list_tool import ListTool
    from nanobot.agent.tools.event_tool import EventTool
    from nanobot.cron.service import CronService

from backend.handler_context import HandlerContext, _reply_confirm_prompt

# ---------------------------------------------------------------------------
# Pedido de contacto com atendimento ao cliente — DeepSeek mensagem empática
# ---------------------------------------------------------------------------

async def handle_atendimento_request(ctx: HandlerContext, content: str) -> str | None:
    """Quando o cliente pede falar com atendimento: registar em painpoints e responder com contacto + mensagem empática (DeepSeek)."""
    from backend.atendimento_contact import is_atendimento_request, build_atendimento_response
    from backend.painpoints_store import add_painpoint

    if not is_atendimento_request(content):
        return None
    add_painpoint(ctx.chat_id, "pedido explícito de contacto")
    user_lang = "pt-BR"
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id)
        finally:
            db.close()
    except Exception:
        pass
    provider = ctx.main_provider or ctx.scope_provider
    model = (ctx.main_model or ctx.scope_model or "").strip()
    if not provider or not model:
        from backend.atendimento_contact import ATENDIMENTO_PHONE, ATENDIMENTO_EMAIL
        return f"Entendemos. Nossa equipe de atendimento está disponível:\n\n📞 {ATENDIMENTO_PHONE}\n📧 {ATENDIMENTO_EMAIL}"
    return await build_atendimento_response(user_lang, provider, model)


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
# /start, /recorrente, /pendente, /hoje, /semana, /tz, /lang, /quiet, /stop
# ---------------------------------------------------------------------------

async def handle_start(ctx: HandlerContext, content: str) -> str | None:
    """/start: opt-in, setup timezone/idioma via texto."""
    if not content.strip().lower().startswith("/start"):
        return None
    return (
        "👋 Olá! Sou o ZapAssist: lembretes, listas e eventos.\n\n"
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


def _is_eventos_unificado_intent(content: str) -> bool:
    """Detecta pedidos de visão unificada: eventos + lembretes."""
    import re
    t = (content or "").strip().lower()
    patterns = [
        r"meus?\s+eventos?",
        r"meus?\s+lembretes?",
        r"meus?\s+lembran[cç]as?",
        r"o\s+que\s+tenho\s+agendado",
        r"lista\s+(de\s+)?(lembretes?|eventos?)",
        r"meus?\s+agendamentos?",
        r"o\s+que\s+(tenho|est[aá]\s+agendado)",
        r"quais?\s+(s[aã]o\s+)?(os\s+)?(meus\s+)?(lembretes?|eventos?)",
    ]
    return any(re.search(p, t) for p in patterns)


async def handle_eventos_unificado(ctx: HandlerContext, content: str) -> str | None:
    """Visão unificada: lembretes (cron) + eventos (filme, livro, etc.)."""
    if not _is_eventos_unificado_intent(content):
        return None

    parts = []

    # Lembretes (cron)
    if ctx.cron_tool:
        ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
        cron_out = await ctx.cron_tool.execute(action="list")
        if "Nenhum lembrete" not in cron_out:
            parts.append(cron_out)
        else:
            parts.append("📅 **Lembretes:** Nenhum agendado.")

    # Eventos (Event model)
    if ctx.event_tool:
        ctx.event_tool.set_context(ctx.channel, ctx.chat_id)
        try:
            event_out = await ctx.event_tool.execute(action="list", tipo="")
        except Exception:
            event_out = "Nenhum evento."
        if isinstance(event_out, str) and "Nenhum" not in event_out:
            parts.append("📋 **Eventos (filmes, livros, etc.):**\n" + event_out)
        else:
            parts.append("📋 **Eventos:** Nenhum registado.")

    if not parts:
        return "Não tens lembretes nem eventos agendados. Queres adicionar algum?"
    return "\n\n".join(parts)


async def handle_pendente(ctx: HandlerContext, content: str) -> str | None:
    """/pendente: tudo aberto (listas com itens não feitos)."""
    if not content.strip().lower().startswith("/pendente"):
        return None
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.list_tool.execute(action="list", list_name="")


async def handle_tz(ctx: HandlerContext, content: str) -> str | None:
    """/tz Cidade ou /tz IANA (ex: /tz Lisboa, /tz Europe/Lisbon). Regista timezone para as horas dos lembretes."""
    import re
    m = re.match(r"^/tz\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return "🌍 Use: /tz Cidade (ex: /tz Lisboa) ou /tz Europe/Lisbon"
    from backend.timezone import city_to_iana, is_valid_iana
    tz_iana = None
    if "/" in raw:
        tz_iana = raw if is_valid_iana(raw) else None
    else:
        tz_iana = city_to_iana(raw)
        if not tz_iana:
            tz_iana = city_to_iana(raw.replace(" ", ""))
    if not tz_iana:
        return f"🌍 Cidade «{raw}» não reconhecida. Tenta: /tz Lisboa, /tz São Paulo ou /tz Europe/Lisbon (IANA)."
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_timezone
        db = SessionLocal()
        try:
            if set_user_timezone(db, ctx.chat_id, tz_iana):
                return f"✅ Timezone definido: {tz_iana}. As horas dos lembretes passam a ser mostradas no teu fuso."
            return "❌ Timezone inválido."
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao gravar timezone: {e}"
    return None


async def handle_lang(ctx: HandlerContext, content: str) -> str | None:
    """/lang pt-pt | pt-br | es | en."""
    import re
    m = re.match(r"^/lang\s+(\S+)\s*$", content.strip(), re.I)
    if not m:
        return None
    lang = m.group(1).strip().lower()
    mapping = {"pt-pt": "pt-PT", "ptpt": "pt-PT", "ptbr": "pt-BR", "pt-br": "pt-BR", "es": "es", "en": "en"}
    code = mapping.get(lang) or (lang if lang in ("pt-PT", "pt-BR", "es", "en") else None)
    if not code:
        return "🌐 Idiomas disponíveis: /lang pt-pt | pt-br | es | en"
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_language
        db = SessionLocal()
        try:
            set_user_language(db, ctx.chat_id, code)
            return f"✅ Idioma definido: {code}."
        finally:
            db.close()
    except Exception:
        return "❌ Erro ao gravar idioma."
    return None


async def handle_quiet(ctx: HandlerContext, content: str) -> str | None:
    """/quiet 22:00-08:00 ou /quiet 22:00 08:00: horário silencioso (não recebes notificações). /quiet off para desativar."""
    import re
    if not content.strip().lower().startswith("/quiet"):
        return None
    rest = content.strip()[6:].strip()
    if not rest or rest.lower() in ("off", "desligar", "não", "nao"):
        try:
            from backend.database import SessionLocal
            from backend.user_store import set_user_quiet
            db = SessionLocal()
            try:
                if set_user_quiet(db, ctx.chat_id, None, None):
                    return "🔔 Horário silencioso desativado. Voltaste a receber notificações a qualquer hora."
            finally:
                db.close()
        except Exception:
            pass
        return "❌ Erro ao desativar."
    parts = re.split(r"[\s\-–—]+", rest, maxsplit=1)
    if len(parts) < 2:
        return "🔇 Usa: /quiet 22:00-08:00 (não notificar entre 22h e 8h) ou /quiet off para desativar."
    start_hhmm, end_hhmm = parts[0].strip(), parts[1].strip()
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_quiet, _parse_time_hhmm
        if _parse_time_hhmm(start_hhmm) is None or _parse_time_hhmm(end_hhmm) is None:
            return "🕐 Horas em HH:MM (ex.: 22:00, 08:00)."
        db = SessionLocal()
        try:
            if set_user_quiet(db, ctx.chat_id, start_hhmm, end_hhmm):
                return f"🔇 Horário silencioso ativo: {start_hhmm}–{end_hhmm}. Não receberás lembretes nessa janela."
        finally:
            db.close()
    except Exception:
        pass
    return "❌ Erro ao guardar. Usa /quiet 22:00-08:00."


async def handle_stop(ctx: HandlerContext, content: str) -> str | None:
    """/stop: opt-out."""
    if not content.strip().lower().startswith("/stop"):
        return None
    return _reply_confirm_prompt(
        "🔕 Quer pausar as mensagens? Vais deixar de receber lembretes e notificações."
    )


async def handle_reset(ctx: HandlerContext, content: str) -> str | None:
    """/reset: limpa dados do onboarding (nome, cidade) para refazer o cadastro."""
    if not content.strip().lower().startswith("/reset"):
        return None
    try:
        from backend.database import SessionLocal
        from backend.user_store import clear_onboarding_data, get_user_language
        from backend.locale import LangCode
        db = SessionLocal()
        try:
            clear_onboarding_data(db, ctx.chat_id)
            lang: LangCode = get_user_language(db, ctx.chat_id) or "pt-BR"
        finally:
            db.close()
    except Exception:
        lang = "pt-BR"
    msgs = {
        "pt-PT": "Cadastro apagado. Na próxima mensagem, recomeço o onboarding (nome, cidade). Respeitamos LGPD: só o essencial. 😊",
        "pt-BR": "Cadastro apagado. Na próxima mensagem, recomeço o cadastro (nome, cidade). Respeitamos LGPD: só o essencial. 😊",
        "es": "Registro borrado. En el próximo mensaje, reinicio (nombre, ciudad). Respetamos RGPD. 😊",
        "en": "Registration cleared. Next message, I'll restart (name, city). We respect GDPR. 😊",
    }
    if ctx.session_manager:
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            for k in ("pending_preferred_name", "pending_language_choice", "pending_city",
                      "onboarding_intro_sent", "onboarding_language_asked"):
                session.metadata.pop(k, None)
            ctx.session_manager.save(session)
        except Exception:
            pass
    return msgs.get(lang, msgs["pt-BR"])


# ---------------------------------------------------------------------------
# /exportar, /deletar_tudo: com confirmação 1=sim 2=não
# ---------------------------------------------------------------------------

async def handle_exportar(ctx: HandlerContext, content: str) -> str | None:
    """/exportar: confirma? 1=sim 2=não."""
    if not content.strip().lower().startswith("/exportar"):
        return None
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "exportar", {})
    return _reply_confirm_prompt("📤 Queres exportar todas as tuas listas e lembretes?")


async def handle_deletar_tudo(ctx: HandlerContext, content: str) -> str | None:
    """/deletar_tudo: confirma? 1=sim 2=não."""
    import re
    if not re.match(r"^/deletar[_\s]?tudo\s*$", content.strip(), re.I):
        return None
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "deletar_tudo", {})
    return _reply_confirm_prompt(
        "⚠️ Apagar TODOS os dados? (listas, lembretes, eventos) — Esta ação não tem volta."
    )


# ---------------------------------------------------------------------------
# Resolver confirmação pendente (1=sim 2=não)
# ---------------------------------------------------------------------------

async def _resolve_confirm(ctx: HandlerContext, content: str) -> str | None:
    from backend.confirmations import get_pending, clear_pending, is_confirm_reply, is_confirm_yes, is_confirm_no
    if not is_confirm_reply(content):
        return None
    pending = get_pending(ctx.channel, ctx.chat_id)
    if not pending:
        return None
    clear_pending(ctx.channel, ctx.chat_id)
    action = pending.get("action")
    if action == "exportar":
        if is_confirm_no(content):
            return "❌ Exportação cancelada."
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_or_create_user
            from backend.models_db import List, ListItem
            db = SessionLocal()
            try:
                user = get_or_create_user(db, ctx.chat_id)
                lists = db.query(List).filter(List.user_id == user.id).all()
                lines = []
                for lst in lists:
                    items = db.query(ListItem).filter(ListItem.list_id == lst.id).all()
                    lines.append(f"[{lst.name}]")
                    for i in items:
                        lines.append(f"  - {i.text}" + (" (feito)" if i.done else ""))
                return "📤 Exportação:\n" + "\n".join(lines) if lines else "📭 Nada para exportar."
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao exportar: {e}"
    if action == "deletar_tudo":
        if is_confirm_no(content):
            return "✅ Cancelado. Nenhum dado foi apagado."
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_or_create_user
            from backend.models_db import List, ListItem, Event
            db = SessionLocal()
            try:
                user = get_or_create_user(db, ctx.chat_id)
                for lst in db.query(List).filter(List.user_id == user.id).all():
                    db.query(ListItem).filter(ListItem.list_id == lst.id).delete()
                    db.delete(lst)
                db.query(Event).filter(Event.user_id == user.id).delete()
                db.commit()
                return "🗑️ Todos os teus dados foram apagados."
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao apagar: {e}"
    if action == "completion_confirmation":
        payload = pending.get("payload") or {}
        job_id = payload.get("job_id")
        completed_job_id = payload.get("completed_job_id") or job_id
        if is_confirm_no(content):
            return "Ok, o lembrete mantém-se. Reage com 👍 quando terminares."
        if is_confirm_yes(content):
            if ctx.cron_service and job_id:
                ctx.cron_service.remove_job_and_deadline_followups(job_id)
                ctx.cron_service.trigger_dependents(completed_job_id)
                return "✅ Marcado como feito!"
            return "Ocorreu um erro. Tenta reagir com 👍 novamente ao lembrete."
        return None
    return None


# ---------------------------------------------------------------------------
# Pedido de lembrete sem tempo (natural language) → solicitar recorrência se recorrente
# ---------------------------------------------------------------------------

async def handle_recurring_prompt(ctx: HandlerContext, content: str) -> str | None:
    """Quando o usuário pede lembrete em linguagem natural sem data (ex: 'lembrar de tomar remédio'), e parece recorrente, pergunta a frequência."""
    from backend.recurring_detector import maybe_ask_recurrence
    from backend.user_store import get_user_language
    from backend.database import SessionLocal
    from backend.locale import LangCode

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
