"""Handlers de comandos EXATAMENTE como no README: /lembrete, /list nome add item, /feito nome id.

- Sem botões interativos (sem Business API): confirmações com texto "1=sim 2=não".
- TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']).
- Persistência em SQLite (user_phone → listas/lembretes) via backend.models_db e cron.
- Baileys via gateway: resposta em texto (client.sendMessage(jid, {text: msg})).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.agent.tools.cron import CronTool
    from nanobot.agent.tools.list_tool import ListTool
    from nanobot.agent.tools.event_tool import EventTool
    from nanobot.cron.service import CronService

from backend.handlers_organizacao import (
    handle_habito,
    handle_habitos,
    handle_meta,
    handle_metas,
    handle_nota,
    handle_notas,
    handle_projeto,
    handle_projetos,
    handle_template,
    handle_templates,
    handle_save,
    handle_bookmark,
    handle_bookmarks,
    handle_find,
)
from backend.handlers_limpeza import handle_limpeza


@dataclass
class HandlerContext:
    """Contexto para handlers: canal, chat, ferramentas (cron, list, event), histórico e Mimo (rever/análises)."""
    channel: str
    chat_id: str
    cron_service: CronService | None
    cron_tool: CronTool | None
    list_tool: ListTool | None
    event_tool: EventTool | None
    session_manager: Any = None  # SessionManager: para «rever conversa»
    scope_provider: Any = None  # LLMProvider (Xiaomi Mimo) para rever histórico e perguntas analíticas
    scope_model: str | None = None  # modelo a usar (ex. xiaomi_mimo/mimo-v2-flash)
    main_provider: Any = None  # LLMProvider (DeepSeek) para mensagens empáticas (ex.: atendimento)
    main_model: str | None = None  # modelo principal do agente


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

def _reply_confirm_prompt(msg: str) -> str:
    """Sufixo padrão para pedir confirmação sem botões."""
    return f"{msg}\n\n1️⃣ Sim  2️⃣ Não"


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
    # list_name vazio no list_tool mostra listas; para "tudo aberto" podemos juntar todas
    # Por agora devolve listas; depois pode agregar itens pendentes de todas.


def _visao_hoje_semana(ctx: HandlerContext, dias: int) -> str:
    """dias=1 para hoje, dias=7 para semana. Retorna texto com lembretes e eventos no período."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import Event

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            today = now.date()
            end_date = today + timedelta(days=dias - 1) if dias > 1 else today
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
            period_end = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=tz)
            today_start_utc_ms = int(today_start.timestamp() * 1000)
            period_end_utc_ms = int(period_end.timestamp() * 1000)

            lines = []
            if dias == 1:
                lines.append("📅 **Hoje**")
            else:
                lines.append(f"📅 **Próximos {dias} dias** (até {end_date.strftime('%d/%m')})")

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
            if reminders:
                for dt, msg in reminders[:15]:
                    lines.append(f"• {dt.strftime('%H:%M')} — {msg[:50]}{'…' if len(msg) > 50 else ''}")
            else:
                lines.append("• Nenhum lembrete agendado.")

            events = db.query(Event).filter(Event.user_id == user.id, Event.deleted == False, Event.data_at.isnot(None)).all()
            event_list = []
            for ev in events:
                if not ev.data_at:
                    continue
                ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
                try:
                    ev_local = ev_date.astimezone(tz).date()
                except Exception:
                    ev_local = ev_date.date()
                if today <= ev_local <= end_date:
                    nome = (ev.payload or {}).get("nome", "") if isinstance(ev.payload, dict) else str(ev.payload)[:40]
                    event_list.append((ev_local, ev.data_at, nome or "Evento"))
            event_list.sort(key=lambda x: (x[0], x[1] or datetime.min))
            if event_list:
                lines.append("")
                for d, _, nome in event_list[:15]:
                    lines.append(f"• {d.strftime('%d/%m')} — {nome[:50]}")
            else:
                if dias == 1:
                    lines.append("• Nenhum evento hoje.")

            return "\n".join(lines) if lines else "Nada para mostrar."
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar visão: {e}"


async def handle_hoje(ctx: HandlerContext, content: str) -> str | None:
    """/hoje: visão rápida do dia (lembretes e eventos de hoje)."""
    if not content.strip().lower().startswith("/hoje"):
        return None
    return _visao_hoje_semana(ctx, 1)


async def handle_semana(ctx: HandlerContext, content: str) -> str | None:
    """/semana: visão rápida da semana (lembretes e eventos nos próximos 7 dias)."""
    if not content.strip().lower().startswith("/semana"):
        return None
    return _visao_hoje_semana(ctx, 7)


def _visao_mes(ctx: HandlerContext, year: int, month: int) -> str:
    """Calendário ASCII do mês com marcadores (*) nos dias com eventos/lembretes."""
    import calendar
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import Event

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)

            first_day = datetime(year, month, 1, tzinfo=tz)
            _, last_dom = calendar.monthrange(year, month)
            last_day = datetime(year, month, last_dom, 23, 59, 59, tzinfo=tz)
            start_ms = int(first_day.timestamp() * 1000)
            end_ms = int(last_day.timestamp() * 1000)

            days_with_activity: set[int] = set()

            if ctx.cron_service:
                for job in ctx.cron_service.list_jobs():
                    if getattr(job.payload, "to", None) != ctx.chat_id:
                        continue
                    nr = getattr(job.state, "next_run_at_ms", None)
                    if nr and start_ms <= nr <= end_ms:
                        dt = datetime.fromtimestamp(nr / 1000, tz=ZoneInfo("UTC")).astimezone(tz)
                        days_with_activity.add(dt.day)

            events = db.query(Event).filter(
                Event.user_id == user.id,
                Event.deleted == False,
                Event.data_at.isnot(None),
            ).all()
            for ev in events:
                if not ev.data_at:
                    continue
                ev_date = ev.data_at if ev.data_at.tzinfo else ev.data_at.replace(tzinfo=ZoneInfo("UTC"))
                try:
                    ev_local = ev_date.astimezone(tz)
                except Exception:
                    ev_local = ev_date
                if ev_local.year == year and ev_local.month == month:
                    days_with_activity.add(ev_local.day)

            cal = calendar.Calendar(firstweekday=6)
            month_name = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"][month - 1]
            lines = [f"       {month_name} {year}", "  D  S  T  Q  Q  S  S"]

            week_lines = []
            for week in cal.monthdayscalendar(year, month):
                row = []
                for d in week:
                    if d == 0:
                        row.append("  ")
                    else:
                        mark = "*" if d in days_with_activity else " "
                        row.append(f"{d:2}{mark}")
                week_lines.append(" ".join(row))
            lines.extend(week_lines)

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar calendário: {e}"


def _visao_timeline(ctx: HandlerContext, dias: int = 7) -> str:
    """Histórico cronológico: lembretes entregues, tarefas feitas, eventos criados."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import Event, ReminderHistory, AuditLog

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            since = now - timedelta(days=dias)
            since_naive = since.astimezone(timezone.utc).replace(tzinfo=None) if since.tzinfo else since

            items: list[tuple[datetime, str]] = []

            for r in (
                db.query(ReminderHistory)
                .filter(
                    ReminderHistory.user_id == user.id,
                    ReminderHistory.status == "sent",
                    ReminderHistory.delivered_at.isnot(None),
                    ReminderHistory.delivered_at >= since_naive,
                )
                .all()
            ):
                ts = r.delivered_at or r.created_at
                if ts:
                    if ts.tzinfo:
                        ts = ts.astimezone(tz)
                    else:
                        ts = ts.replace(tzinfo=timezone.utc).astimezone(tz)
                    msg = (r.message or "")[:45] + ("…" if len(r.message or "") > 45 else "")
                    items.append((ts, f"Lembrete: {msg} ✓"))

            for a in (
                db.query(AuditLog)
                .filter(
                    AuditLog.user_id == user.id,
                    AuditLog.action.in_(("list_feito", "list_add", "list_remove")),
                    AuditLog.created_at >= since_naive,
                )
                .all()
            ):
                ts = a.created_at
                if ts and ts.tzinfo:
                    ts = ts.astimezone(tz)
                elif ts:
                    ts = ts.replace(tzinfo=timezone.utc).astimezone(tz)
                if ts:
                    if a.action == "list_feito":
                        items.append((ts, f"Feito: {a.resource or '?'}"))
                    elif a.action == "list_add":
                        items.append((ts, f"Add: {a.resource or '?'}"))
                    elif a.action == "list_remove":
                        items.append((ts, f"Removido: {a.resource or '?'}"))

            for ev in (
                db.query(Event)
                .filter(Event.user_id == user.id, Event.deleted == False, Event.created_at >= since_naive)
                .all()
            ):
                ts = ev.created_at
                if ts and ts.tzinfo:
                    ts = ts.astimezone(tz)
                elif ts:
                    ts = ts.replace(tzinfo=timezone.utc).astimezone(tz)
                if ts:
                    nome = (ev.payload or {}).get("nome", "") if isinstance(ev.payload, dict) else str(ev.payload)[:40]
                    items.append((ts, f"Evento: {nome or ev.tipo}"))

            items.sort(key=lambda x: x[0], reverse=True)
            lines = [f"📜 **Timeline** (últimos {dias} dias)"]
            for ts, label in items[:25]:
                lines.append(f"• {ts.strftime('%d/%m %H:%M')} — {label}")
            if not items:
                lines.append("• Nada nos últimos dias.")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar timeline: {e}"


def _visao_stats(ctx: HandlerContext, mode: str = "resumo") -> str:
    """Estatísticas: tarefas feitas (list_feito) e lembretes recebidos (ReminderHistory sent)."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import ReminderHistory, AuditLog

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            today = now.date()
            since_naive = (now - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)

            def _to_local_date(dt):
                if not dt:
                    return None
                if dt.tzinfo:
                    return dt.astimezone(tz).date()
                return dt.replace(tzinfo=timezone.utc).astimezone(tz).date()

            feito_today = feito_week = rem_today = rem_week = 0
            feito_by_day: dict[str, int] = {}
            rem_by_day: dict[str, int] = {}

            for a in db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.action == "list_feito",
                AuditLog.created_at >= since_naive,
            ).all():
                d = _to_local_date(a.created_at)
                if d:
                    feito_by_day[d.isoformat()] = feito_by_day.get(d.isoformat(), 0) + 1
                    if d == today:
                        feito_today += 1
                    if (today - d).days < 7:
                        feito_week += 1

            for r in db.query(ReminderHistory).filter(
                ReminderHistory.user_id == user.id,
                ReminderHistory.status == "sent",
                ReminderHistory.delivered_at.isnot(None),
                ReminderHistory.delivered_at >= since_naive,
            ).all():
                d = _to_local_date(r.delivered_at)
                if d:
                    rem_by_day[d.isoformat()] = rem_by_day.get(d.isoformat(), 0) + 1
                    if d == today:
                        rem_today += 1
                    if (today - d).days < 7:
                        rem_week += 1

            lines = ["📊 **Estatísticas**"]
            if mode == "resumo":
                lines.append(f"Hoje: {feito_today} tarefas feitas | {rem_today} lembretes")
                lines.append(f"Esta semana: {feito_week} tarefas | {rem_week} lembretes")
            elif mode == "dia":
                lines.append("Últimos 7 dias:")
                for i in range(6, -1, -1):
                    d = today - timedelta(days=i)
                    fd = feito_by_day.get(d.isoformat(), 0)
                    rd = rem_by_day.get(d.isoformat(), 0)
                    lines.append(f"• {d.strftime('%d/%m')} — {fd} tarefas | {rd} lembretes")
            elif mode == "semana":
                lines.append("Últimas 4 semanas:")
                for i in range(4):
                    start = today - timedelta(days=6 + i * 7)
                    end = today - timedelta(days=i * 7)
                    fd = sum(feito_by_day.get((today - timedelta(days=i * 7 + j)).isoformat(), 0) for j in range(7))
                    rd = sum(rem_by_day.get((today - timedelta(days=i * 7 + j)).isoformat(), 0) for j in range(7))
                    lines.append(f"• S{i + 1} ({start.strftime('%d/%m')}–{end.strftime('%d/%m')}): {fd} tarefas | {rd} lembretes")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar estatísticas: {e}"


def _visao_produtividade(ctx: HandlerContext, mode: str = "semana") -> str:
    """Relatório de produtividade: evolução semanal ou mensal (tarefas, lembretes, eventos)."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    from backend.database import SessionLocal
    from backend.user_store import get_or_create_user, get_user_timezone
    from backend.models_db import ReminderHistory, AuditLog, Event

    try:
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id)
            tz_iana = get_user_timezone(db, ctx.chat_id)
            try:
                tz = ZoneInfo(tz_iana)
            except Exception:
                tz = ZoneInfo("UTC")
            now = datetime.now(tz)
            today = now.date()
            since_naive = (now - timedelta(days=93)).astimezone(timezone.utc).replace(tzinfo=None)

            def _to_local_date(dt):
                if not dt:
                    return None
                if dt.tzinfo:
                    return dt.astimezone(tz).date()
                return dt.replace(tzinfo=timezone.utc).astimezone(tz).date()

            feito_by_day: dict[str, int] = {}
            rem_by_day: dict[str, int] = {}
            ev_by_day: dict[str, int] = {}

            for a in db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.action == "list_feito",
                AuditLog.created_at >= since_naive,
            ).all():
                d = _to_local_date(a.created_at)
                if d:
                    feito_by_day[d.isoformat()] = feito_by_day.get(d.isoformat(), 0) + 1

            for r in db.query(ReminderHistory).filter(
                ReminderHistory.user_id == user.id,
                ReminderHistory.status == "sent",
                ReminderHistory.delivered_at.isnot(None),
                ReminderHistory.delivered_at >= since_naive,
            ).all():
                d = _to_local_date(r.delivered_at)
                if d:
                    rem_by_day[d.isoformat()] = rem_by_day.get(d.isoformat(), 0) + 1

            for ev in db.query(Event).filter(
                Event.user_id == user.id,
                Event.deleted == False,
                Event.created_at >= since_naive,
            ).all():
                d = _to_local_date(ev.created_at)
                if d:
                    ev_by_day[d.isoformat()] = ev_by_day.get(d.isoformat(), 0) + 1

            month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            lines = ["📊 **Relatório de produtividade**"]
            if mode == "semana":
                lines.append("Últimas 4 semanas:")
                for i in range(4):
                    start = today - timedelta(days=6 + i * 7)
                    end = today - timedelta(days=i * 7)
                    fd = sum(feito_by_day.get((start + timedelta(days=j)).isoformat(), 0) for j in range(7))
                    rd = sum(rem_by_day.get((start + timedelta(days=j)).isoformat(), 0) for j in range(7))
                    ed = sum(ev_by_day.get((start + timedelta(days=j)).isoformat(), 0) for j in range(7))
                    lines.append(f"• S{i + 1} ({start.strftime('%d/%m')}–{end.strftime('%d/%m')}): {fd} tarefas | {rd} lembretes | {ed} eventos")
            else:
                lines.append("Últimos 3 meses:")
                for i in range(3):
                    m = today.month - 1 - i
                    y = today.year
                    while m < 1:
                        m += 12
                        y -= 1
                    start = datetime(y, m, 1, tzinfo=tz).date()
                    _, last_dom = __import__("calendar").monthrange(y, m)
                    end = datetime(y, m, last_dom, tzinfo=tz).date()
                    fd = rd = ed = 0
                    d = start
                    while d <= end and d <= today:
                        fd += feito_by_day.get(d.isoformat(), 0)
                        rd += rem_by_day.get(d.isoformat(), 0)
                        ed += ev_by_day.get(d.isoformat(), 0)
                        d += timedelta(days=1)
                    lines.append(f"• {month_names[m - 1]} {y}: {fd} tarefas | {rd} lembretes | {ed} eventos")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao carregar relatório: {e}"


async def handle_stats(ctx: HandlerContext, content: str) -> str | None:
    """/stats ou /stats dia ou /stats semana: estatísticas de tarefas feitas e lembretes."""
    import re
    t = content.strip().lower()
    if not t.startswith("/stats"):
        return None
    rest = t[6:].strip()
    mode = "resumo"
    if rest == "dia":
        mode = "dia"
    elif rest == "semana":
        mode = "semana"
    return _visao_stats(ctx, mode)


async def handle_produtividade(ctx: HandlerContext, content: str) -> str | None:
    """/produtividade ou /produtividade mes: relatório de produtividade (tarefas, lembretes, eventos) por semana ou mês."""
    t = content.strip().lower()
    if not t.startswith("/produtividade"):
        return None
    rest = t[14:].strip()
    mode = "semana"
    if rest == "mes" or rest == "mês":
        mode = "mes"
    return _visao_produtividade(ctx, mode)


def _visao_revisao_semanal(ctx: HandlerContext) -> str:
    """Resumo da semana (últimos 7 dias): tarefas, lembretes, eventos."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
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


async def handle_revisao(ctx: HandlerContext, content: str) -> str | None:
    """/revisao ou /revisao-semana: resumo da semana (tarefas, lembretes, eventos)."""
    t = content.strip().lower()
    if not t.startswith("/revisao"):
        return None
    return _visao_revisao_semanal(ctx)


async def handle_timeline(ctx: HandlerContext, content: str) -> str | None:
    """/timeline ou /timeline 14: histórico cronológico (lembretes, tarefas, eventos)."""
    import re
    t = content.strip().lower()
    if not t.startswith("/timeline"):
        return None
    rest = t[9:].strip()
    dias = 7
    if rest:
        m = re.match(r"^(\d+)\s*$", rest)
        if m:
            dias = min(30, max(1, int(m.group(1))))
    return _visao_timeline(ctx, dias)


async def handle_mes(ctx: HandlerContext, content: str) -> str | None:
    """/mes ou /mes 3 ou /mes 2026-03: calendário do mês com eventos e lembretes."""
    import re
    t = content.strip().lower()
    if not t.startswith("/mes"):
        return None
    rest = t[4:].strip()
    now = __import__("datetime").datetime.now()
    year, month = now.year, now.month
    if rest:
        m = re.match(r"^(\d{1,2})\s*$", rest)
        if m:
            month = min(12, max(1, int(m.group(1))))
        else:
            m = re.match(r"^(\d{4})-(\d{1,2})\s*$", rest)
            if m:
                year = int(m.group(1))
                month = min(12, max(1, int(m.group(2))))
    return _visao_mes(ctx, year, month)


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
# Mimo: chamada ao LLM (Xiaomi) para formatar rever e análises
# ---------------------------------------------------------------------------

async def _call_mimo(
    ctx: HandlerContext,
    user_lang: str,
    instruction: str,
    data_text: str,
    max_tokens: int = 420,
) -> str | None:
    """Chama o Mimo (scope_provider) para gerar resposta. Retorna None se não houver provider."""
    if not ctx.scope_provider or not ctx.scope_model:
        return None
    try:
        lang_instruction = {
            "pt-PT": "Responde em português de Portugal. Resposta curta (1-2 frases).",
            "pt-BR": "Responde em português do Brasil. Resposta curta (1-2 frases).",
            "es": "Responde en español. Respuesta corta (1-2 frases).",
            "en": "Respond in English. Short answer (1-2 sentences).",
        }.get(user_lang, "Respond in the user's language. Short answer (1-2 sentences).")
        prompt = f"{instruction}\n\n{lang_instruction}\n\nDados:\n{data_text}"
        r = await ctx.scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=ctx.scope_model,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        out = (r.content or "").strip()
        return out if out else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rever: últimas 10/20/50/100 mensagens, todo o histórico ou lembretes — com Mimo
# ---------------------------------------------------------------------------

def _parse_rever_intent(content: str) -> tuple[str | None, int | None]:
    """
    Retorna (tipo, N ou None).
    tipo: "conversa" | "lembretes" | "pedido" | "lembrete" | "rever_geral" | None
    N: 10, 20, 50, 100 para conversa; None = todo ou não aplicável.
    """
    import re
    t = (content or "").strip().lower()
    if not t:
        return None, None
    # Número explícito: "rever últimas 20", "rever 50 mensagens", "rever 10"
    m = re.search(r"rever\s+(?:últimas?\s+)?(\d+)\s*(?:mensagens?)?", t)
    if m:
        n = int(m.group(1))
        if n <= 0:
            return "conversa", 10
        if n > 500:
            n = 500
        return "conversa", n
    if re.search(r"rever\s+todo\s+(o\s+)?hist[oó]rico|hist[oó]rico\s+completo|todo\s+o\s+hist[oó]rico", t):
        return "conversa", None  # None = todo
    if re.search(r"rever\s+(a\s+)?conversa|rever\s+hist[oó]rico|rever\s+mensagens|hist[oó]rico\s+da\s+conversa", t):
        return "conversa", 20  # default
    if re.search(r"rever\s+lembretes?|rever\s+lembran[cç]as|listar\s+lembretes", t):
        return "lembretes", None
    if re.search(r"rever\s+(o\s+)?pedido|qual\s+era\s+o\s+pedido|o\s+que\s+pedi", t):
        return "pedido", None
    if re.search(r"rever\s+(a\s+)?lembran[cç]a|rever\s+lembrete|qual\s+foi\s+a\s+lembran[cç]a|o\s+que\s+me\s+lembraste", t):
        return "lembrete", None
    if re.search(r"^rever\s*$", t) or t.strip() == "rever":
        return "rever_geral", None
    return None, None


async def handle_rever(ctx: HandlerContext, content: str) -> str | None:
    """Rever conversa (10/20/50/100/todo), lembretes ou último pedido/lembrete. Usa Mimo para formatar."""
    import re
    intent, N = _parse_rever_intent(content)
    if intent is None:
        return None

    user_lang = "en"
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

    # --- Rever conversa (últimas N ou todo) ---
    if intent == "conversa":
        if not ctx.session_manager:
            return "Histórico da conversa não está disponível neste contexto."
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            total = len(session.messages) if hasattr(session, "messages") else 0
            if total == 0:
                return "Ainda não há mensagens nesta conversa."
            # Todo o histórico (máx. 500 para caber no contexto) ou últimas N
            if N is None:
                recent = session.messages[-500:] if len(session.messages) > 500 else list(session.messages)
            else:
                recent = session.messages[-N:] if len(session.messages) > N else list(session.messages)
            lines = []
            for m in recent:
                role = m.get("role", "")
                cont = (m.get("content") or "").strip()
                ts = m.get("timestamp", "")
                label = "Utilizador" if role == "user" else "Assistente"
                if ts:
                    lines.append(f"[{label}] {cont} (timestamp: {ts})")
                else:
                    lines.append(f"[{label}] {cont}")
            data_text = "\n".join(lines)
            if N is not None:
                instruction = f"Resume as últimas {len(recent)} mensagens (total: {total}). Respostas curtas (1-2 frases). Sem inventar."
            else:
                instruction = f"Resume o histórico ({len(recent)} mensagens). Curto e direto."
            out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=560)
            if out:
                return out
            # Fallback sem Mimo
            if total > len(recent):
                header = f"Últimas {len(recent)} de {total} mensagens:\n"
            else:
                header = "Mensagens:\n"
            return header + "\n".join(f"{'Tu' if m.get('role')=='user' else 'Eu'}: {(m.get('content') or '')[:150]}" for m in recent[:30])
        except Exception as e:
            return f"Erro ao buscar conversa: {e}"

    # --- Rever lembretes (lista: Pedido | Agendado para | Status) ---
    if intent == "lembretes":
        try:
            from backend.database import SessionLocal
            from backend.reminder_history import get_reminder_history
            db = SessionLocal()
            try:
                entries = get_reminder_history(db, ctx.chat_id, kind=None, limit=50)
                if not entries:
                    return "Ainda não tens lembretes registados (pedidos agendados ou entregues)."
                data_lines = []
                for e in entries:
                    pedido = (e.get("message") or "").strip() or "(sem texto)"
                    agendado = ""
                    if e.get("schedule_at"):
                        agendado = e["schedule_at"].strftime("%d/%m/%Y %H:%M")
                    elif e.get("created_at"):
                        agendado = e["created_at"].strftime("%d/%m/%Y %H:%M") + " (pedido)"
                    status = e.get("status") or ("agendado" if e["kind"] == "scheduled" else "entregue")
                    if status == "sent":
                        status = "entregue"
                        if e.get("delivered_at"):
                            agendado = agendado or e["delivered_at"].strftime("%d/%m/%Y %H:%M") + " (disparou)"
                    elif status == "failed":
                        status = "falhou"
                    elif status == "scheduled":
                        status = "agendado"
                    data_lines.append(f"Pedido: {pedido} | Agendado para: {agendado} | Status: {status}")
                data_text = "\n".join(data_lines)
                instruction = (
                    "Lista de lembretes: Pedido | Agendado | Status. Apresenta de forma concisa, por data."
                )
                out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=350)
                if out:
                    return out
                return "Lembretes:\n" + "\n".join(data_lines[:20])
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao buscar lembretes: {e}"

    # --- Rever pedido / lembrete (último) ou rever geral ---
    try:
        from backend.database import SessionLocal
        from backend.reminder_history import get_last_scheduled, get_last_delivered
        db = SessionLocal()
        try:
            last_pedido = get_last_scheduled(db, ctx.chat_id)
            last_lembrete = get_last_delivered(db, ctx.chat_id)
            data_parts = []
            if last_pedido:
                data_parts.append(f"Último pedido agendado: {last_pedido}")
            if last_lembrete:
                data_parts.append(f"Última lembrança entregue: {last_lembrete}")
            if not data_parts:
                return "Ainda não tens pedidos nem lembranças registados."
            data_text = "\n".join(data_parts)
            if intent == "pedido":
                instruction = "Indica o último pedido de lembrete. Uma frase."
            elif intent == "lembrete":
                instruction = "Indica a última lembrança entregue. Uma frase."
            else:
                instruction = "Apresenta último pedido e última lembrança. 1-2 frases."
            out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=210)
            if out:
                return out
            if intent == "pedido":
                return f"Foi este o pedido: «{last_pedido}»" if last_pedido else "Ainda não tens nenhum pedido registado."
            if intent == "lembrete":
                return f"Foi esta a lembrança: «{last_lembrete}»" if last_lembrete else "Ainda não recebeste nenhuma lembrança."
            return "\n".join(data_parts)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao buscar: {e}"
    return None


# ---------------------------------------------------------------------------
# Criptomoedas — cotação atual via CoinGecko (API gratuita)
# ---------------------------------------------------------------------------

def _is_crypto_intent(content: str) -> bool:
    """Detecta se o utilizador pergunta sobre criptomoedas."""
    import re
    t = (content or "").strip().lower()
    if not t or len(t) < 4:
        return False
    patterns = [
        r"bitcoin|btc\b",
        r"ethereum|eth\b",
        r"tether|usdt\b",
        r"xrp\b",
        r"bnb\b",
        r"cripto(?:moeda|s)?",
        r"cota[cç][aã]o\s+(?:de\s+)?(?:cripto|bitcoin|eth)",
        r"pre[cç]o\s+(?:do\s+)?(?:bitcoin|eth|cripto)",
        r"quanto\s+(?:est[aá]|vale)\s+(?:o\s+)?(?:bitcoin|eth)",
        r"valor\s+(?:do\s+)?(?:bitcoin|eth|cripto)",
    ]
    return any(re.search(p, t) for p in patterns)


# ---------------------------------------------------------------------------
# Livros sagrados — passagens via APIs gratuitas (só quando pedido diretamente)
# ---------------------------------------------------------------------------

def _is_sacred_text_intent(content: str) -> bool:
    """Detecta pedido explícito de passagem da Bíblia ou Alcorão."""
    import re
    t = (content or "").strip().lower()
    if not t or len(t) < 8:
        return False
    patterns = [
        r"passagem\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"vers[ií]culo\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"(?:quero|d[aá]-?me|manda|mostra)\s+(?:uma\s+)?(?:passagem|vers[ií]culo)\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"(?:b[ií]blia|alcor[aã]o)\s*[:\-]?\s*(?:passagem|vers[ií]culo|random|aleat[oó]ria)",
        r"(?:uma\s+)?passagem\s+(?:aleat[oó]ria|random)\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"vers[ií]culo\s+(?:de\s+)?(?:jo[aã]o|genesis|mateus|sura)\s+\d",
    ]
    return any(re.search(p, t) for p in patterns)


async def handle_sacred_text(ctx: HandlerContext, content: str) -> str | None:
    """
    Passagens da Bíblia ou Alcorão. Só quando o cliente pede diretamente.
    Usa Mimo para confirmar contexto; inclui lembrete do organizador.
    """
    if not _is_sacred_text_intent(content):
        return None
    if not ctx.scope_provider or not ctx.scope_model:
        return None

    # Mimo: confirmar que é pedido explícito (evitar parecer pastoral em menções casuais)
    from backend.sacred_texts import (
        fetch_bible_verse, fetch_bible_random,
        fetch_quran_verse, fetch_quran_random,
        parse_bible_reference, parse_quran_reference,
        build_sacred_response,
    )
    try:
        prompt = (
            f"Mensagem do utilizador: «{content[:300]}»\n"
            "O utilizador está a pedir EXPLICITAMENTE uma passagem ou versículo da Bíblia ou do Alcorão? "
            "(não conta: 'fui à igreja', 'li o alcorão ontem', menções casuais). Responde apenas: SIM ou NAO"
        )
        r = await ctx.scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=ctx.scope_model,
            max_tokens=10,
            temperature=0,
        )
        raw = (r.content or "").strip().upper()
        if "NAO" in raw or "NÃO" in raw.upper() or raw.startswith("N"):
            return None
    except Exception:
        pass

    t = (content or "").strip().lower()
    reminder = "Também posso ajudar com lembretes e organização quando precisares."
    data = None
    book = ""

    if "alcor" in t or "alcorão" in t or "quran" in t:
        q_ref = parse_quran_reference(content)
        if q_ref:
            data = fetch_quran_verse(q_ref[0], q_ref[1])
        else:
            data = fetch_quran_random()
        book = "quran"
    elif "bíblia" in t or "biblia" in t or "bible" in t:
        b_ref = parse_bible_reference(content)
        if b_ref:
            data = fetch_bible_verse(b_ref)
        else:
            data = fetch_bible_random()
        book = "bible"
    else:
        return None

    return build_sacred_response(book, data, reminder)


async def handle_crypto(ctx: HandlerContext, content: str) -> str | None:
    """Quando o utilizador fala de cripto, responde com cotação atual (BTC, ETH, USDT, XRP, BNB)."""
    if not _is_crypto_intent(content):
        return None
    from backend.crypto_prices import fetch_crypto_prices, build_crypto_message
    data = fetch_crypto_prices()
    return build_crypto_message(data)


# ---------------------------------------------------------------------------
# "Sobre o que estávamos falando?" — resumo da conversa com Mimo
# ---------------------------------------------------------------------------

def _is_resumo_conversa_intent(content: str) -> bool:
    """Detecta pedidos explícitos de resumo da conversa (não lembretes)."""
    import re
    t = (content or "").strip().lower()
    if not t or len(t) < 8:
        return False
    patterns = [
        r"sobre\s+o\s+que\s+(est[aá]vamos|estamos)\s+falando",
        r"o\s+que\s+fal[aá]mos",
        r"o\s+que\s+(estava|estava[va]mos)\s+(a\s+)?falando",
        r"resumo\s+da\s+conversa",
        r"resumir\s+o\s+que\s+falamos",
        r"do\s+que\s+falamos",
        r"o\s+que\s+discutimos",
        r"o\s+que\s+conversamos",
        r"lembra\s+(do\s+que|o\s+que)\s+falamos",
        r"em\s+que\s+ponto\s+paramos",
        r"onde\s+paramos",
        r"retomar\s+(de\s+onde|a\s+conversa)",
    ]
    return any(re.search(p, t) for p in patterns)


async def handle_resumo_conversa(ctx: HandlerContext, content: str) -> str | None:
    """«Sobre o que estávamos falando?», «resumo da conversa» — usa sessão + Mimo."""
    if not _is_resumo_conversa_intent(content):
        return None
    if not ctx.session_manager or not ctx.scope_provider or not ctx.scope_model:
        return None

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    total = len(session.messages) if hasattr(session, "messages") else 0
    if total == 0:
        user_lang = "pt-BR"
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language
            db = SessionLocal()
            try:
                user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
            finally:
                db.close()
            lang_msg = {
                "pt-PT": "Ainda não há mensagens nesta conversa.",
                "pt-BR": "Ainda não há mensagens nesta conversa.",
                "es": "Aún no hay mensajes en esta conversación.",
                "en": "No messages in this conversation yet.",
            }
            return lang_msg.get(user_lang, lang_msg["pt-BR"])
        except Exception:
            return "Ainda não há mensagens nesta conversa."

    recent = session.messages[-30:] if len(session.messages) > 30 else list(session.messages)
    lines = []
    for m in recent:
        role = m.get("role", "")
        cont = (m.get("content") or "").strip()
        label = "Utilizador" if role == "user" else "Assistente"
        lines.append(f"[{label}] {cont}")
    data_text = "\n".join(lines) if lines else ""

    user_lang = "pt-BR"
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
        finally:
            db.close()
    except Exception:
        pass

    instruction = (
        "O utilizador quer um resumo do que estava a ser falado na conversa. "
        "Resume as mensagens seguintes em 2-4 frases curtas. Foco no essencial: lembretes, listas, decisões, pedidos. Sem inventar."
    )
    out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=280)
    if out:
        return out
    # Fallback: primeiras linhas
    return "Últimos temas:\n" + "\n".join(lines[:8]) if lines else "Nada a resumir."


# ---------------------------------------------------------------------------
# Perguntas analíticas (quantos lembretes, horas mais comuns, resumos) — Mimo
# ---------------------------------------------------------------------------

def is_analytical_message(content: str) -> bool:
    """True se a mensagem for analítica. Escolhe Mimo quando: muita lógica/raciocínio, análises de histórico, velocidade crítica."""
    return _is_analytics_intent(content)


def _is_analytics_intent(content: str) -> bool:
    """Detecta se a mensagem é uma pergunta analítica sobre histórico/lembretes."""
    import re
    t = (content or "").strip().lower()
    if not t or len(t) < 10:
        return False
    patterns = [
        r"quantos?\s+lembretes?",
        r"quantas?\s+vezes",
        r"quantas?\s+mensagens?",
        r"esta\s+semana",
        r"este\s+m[eê]s",
        r"resumo\s+(da\s+)?(semana|conversa|lembretes?)",
        r"an[aá]lise\s+(dos?\s+)?(lembretes?|hist[oó]rico)",
        r"estat[íi]sticas?",
        r"horas?\s+mais\s+comuns?",
        r"quais\s+as\s+horas?",
        r"que\s+horas?",
        r"em\s+que\s+horas?",
        r"resumir\s+(a\s+)?conversa",
        r"analisar\s+(os\s+)?lembretes?",
    ]
    return any(re.search(p, t) for p in patterns)


async def handle_analytics(ctx: HandlerContext, content: str) -> str | None:
    """Perguntas analíticas sobre histórico (quantos lembretes, horas comuns, resumos). Usa Mimo."""
    if not _is_analytics_intent(content):
        return None

    user_lang = "en"
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

    from datetime import datetime, timedelta
    from backend.database import SessionLocal
    from backend.reminder_history import get_reminder_history

    db = SessionLocal()
    try:
        # "Esta semana" = desde segunda-feira
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        entries = get_reminder_history(db, ctx.chat_id, kind=None, limit=100, since=week_start)
        # Também buscar últimos 7 dias para perguntas tipo "últimos dias"
        week_ago = now - timedelta(days=7)
        entries_7d = get_reminder_history(db, ctx.chat_id, kind=None, limit=100, since=week_ago)
    finally:
        db.close()

    # Dados para o Mimo: lembretes com data/hora para análises de "horas mais comuns"
    def _format_entries(ents: list) -> str:
        lines = []
        for e in ents:
            k = "agendado" if e["kind"] == "scheduled" else "entregue"
            created = e.get("created_at")
            if created:
                ts = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else str(created)
            else:
                ts = ""
            lines.append(f"{k}\t{ts}\t{e.get('message', '')}")
        return "\n".join(lines)

    data_week = _format_entries(entries)
    data_7d = _format_entries(entries_7d)
    total_week = len(entries)
    total_7d = len(entries_7d)

    # Incluir contagem de mensagens na conversa se disponível
    msg_count = 0
    if ctx.session_manager:
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            msg_count = len(session.messages) if hasattr(session, "messages") else 0
        except Exception:
            pass

    data_text = (
        f"Lembretes desde início da semana (UTC): {total_week} entradas.\n"
        f"Lembretes últimos 7 dias: {total_7d} entradas.\n"
        f"Total de mensagens na conversa (sessão): {msg_count}.\n\n"
        "Lista de lembretes (tipo, data/hora, mensagem):\n"
        f"{data_7d or '(nenhum)'}"
    )

    instruction = (
        "Pergunta analítica sobre lembretes/dados. Resposta curta (1-3 frases). Com números se pedido. Sem inventar."
    )
    question = (content or "").strip()
    full_instruction = f"{instruction}\n\nPergunta do utilizador: «{question}»"

    out = await _call_mimo(ctx, user_lang, full_instruction, data_text, max_tokens=350)
    if out:
        return out
    # Fallback: resposta mínima
    if total_7d == 0:
        return "Ainda não há lembretes registados neste período para analisar."
    return f"Esta semana: {total_week} lembretes. Últimos 7 dias: {total_7d} lembretes. (Resposta detalhada requer Mimo.)"


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


# ---------------------------------------------------------------------------
# Router: confirmação pendente → parse → handlers
# ---------------------------------------------------------------------------

async def route(ctx: HandlerContext, content: str) -> str | None:
    """Despacha mensagem para o handler adequado. Retorna texto de resposta ou None (fallback LLM).
    Escolhe Mimo se: muita lógica (cálculos, otimizações), análises de histórico, velocidade crítica; senão DeepSeek."""
    if not content or not content.strip():
        return None
    text = content.strip()

    reply = await _resolve_confirm(ctx, text)
    if reply is not None:
        return reply

    handlers = [
        handle_atendimento_request,   # «Quero falar com atendimento» → DeepSeek empático + contacto
        handle_pending_confirmation,  # «Quero sim» após oferta de lembrete — Mimo
        handle_eventos_unificado,    # «Meus eventos» = lembretes + eventos
        handle_recurring_prompt,      # «lembrar de tomar remédio» sem tempo → pedir recorrência
        handle_lembrete,
        handle_list,
        handle_feito,
        handle_add,
        handle_done,
        handle_start,
        handle_help,
        handle_recorrente,
        handle_pendente,
        handle_hoje,
        handle_semana,
        handle_mes,
        handle_timeline,
        handle_stats,
        handle_produtividade,
        handle_revisao,
        handle_habitos,
        handle_habito,
        handle_metas,
        handle_meta,
        handle_notas,
        handle_nota,
        handle_projetos,
        handle_projeto,
        handle_templates,
        handle_template,
        handle_bookmarks,
        handle_bookmark,
        handle_save,
        handle_find,
        handle_limpeza,
        handle_sacred_text,  # passagens Bíblia/Alcorão (só quando pedido)
        handle_crypto,  # cotação de cripto (CoinGecko)
        handle_tz,
        handle_lang,
        handle_resumo_conversa,  # "sobre o que estávamos falando?" → sessão + Mimo
        handle_analytics,  # "quantos lembretes esta semana?" etc.
        handle_rever,
        handle_quiet,
        handle_stop,
        handle_reset,
        handle_exportar,
        handle_deletar_tudo,
    ]
    for h in handlers:
        try:
            out = await h(ctx, content)
            if out is not None:
                return out
        except Exception:
            continue
    return None
