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


# ---------------------------------------------------------------------------
# Confirmações (1=sim 2=não). Sem botões.
# ---------------------------------------------------------------------------

def _reply_confirm_prompt(msg: str) -> str:
    """Sufixo padrão para pedir confirmação sem botões."""
    return f"{msg}\n\n1=sim  2=não"


# ---------------------------------------------------------------------------
# Handlers por comando (README: /lembrete, /list, /feito)
# ---------------------------------------------------------------------------

async def handle_lembrete(ctx: HandlerContext, content: str) -> str | None:
    """/lembrete [msg] [data/hora]. Ex: /lembrete reunião amanhã 14h."""
    from backend.command_parser import parse
    from backend.guardrails import is_absurd_request
    intent = parse(content)
    if not intent or intent.get("type") != "lembrete":
        return None
    if is_absurd_request(content):
        return is_absurd_request(content)
    if not ctx.cron_service or not ctx.cron_tool:
        return None
    msg_text = (intent.get("message") or "").strip()
    if not msg_text:
        return None
    in_sec = intent.get("in_seconds")
    every_sec = intent.get("every_seconds")
    cron_expr = intent.get("cron_expr")
    if not (in_sec or every_sec or cron_expr):
        return None
    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        in_seconds=in_sec,
        every_seconds=every_sec,
        cron_expr=cron_expr,
    )


async def handle_list(ctx: HandlerContext, content: str) -> str | None:
    """/list nome add item ou /list [nome]."""
    from backend.command_parser import parse
    intent = parse(content)
    if not intent or intent.get("type") not in ("list_add", "list_show"):
        return None
    if not ctx.list_tool:
        return None
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
    if list_name is None:
        return "Use: /feito nome_da_lista id (ex: /feito mercado 1)"
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.list_tool.execute(action="feito", list_name=list_name, item_id=item_id)


async def handle_filme(ctx: HandlerContext, content: str) -> str | None:
    """/filme Nome."""
    from backend.command_parser import parse
    from backend.guardrails import is_absurd_request
    intent = parse(content)
    if not intent or intent.get("type") != "filme":
        return None
    if is_absurd_request(content) or is_absurd_request(intent.get("nome", "") or ""):
        return is_absurd_request(content) or is_absurd_request(intent.get("nome", "") or "")
    if not ctx.event_tool:
        return None
    ctx.event_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.event_tool.execute(action="add", tipo="filme", nome=intent.get("nome", ""))


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
        "Olá! Sou o ZapAssist: lembretes, listas e eventos.\n"
        "Comandos: /lembrete, /list, /add, /done, /filme.\n"
        "Para timezone: /tz Cidade  |  Idioma: /lang pt-pt ou pt-br ou es ou en."
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
    if not (every_sec or cron_expr):
        return "Use algo como: /recorrente academia segunda 7h  ou  /recorrente beber água a cada 1 hora"
    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
    return await ctx.cron_tool.execute(
        action="add",
        message=msg_text,
        every_seconds=every_sec,
        cron_expr=cron_expr,
    )


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


async def handle_hoje(ctx: HandlerContext, content: str) -> str | None:
    """/hoje: visão rápida do dia (lembretes hoje)."""
    if not content.strip().lower().startswith("/hoje"):
        return None
    return "Visão /hoje: em breve. Use /list para ver listas e lembretes agendados."


async def handle_semana(ctx: HandlerContext, content: str) -> str | None:
    """/semana: visão rápida da semana."""
    if not content.strip().lower().startswith("/semana"):
        return None
    return "Visão /semana: em breve. Use /list para ver listas."


async def handle_tz(ctx: HandlerContext, content: str) -> str | None:
    """/tz Cidade ou /tz IANA (ex: /tz Lisboa, /tz Europe/Lisbon). Regista timezone para as horas dos lembretes."""
    import re
    m = re.match(r"^/tz\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return "Use: /tz Cidade (ex: /tz Lisboa) ou /tz Europe/Lisbon"
    from backend.timezone import city_to_iana, is_valid_iana
    tz_iana = None
    if "/" in raw:
        tz_iana = raw if is_valid_iana(raw) else None
    else:
        tz_iana = city_to_iana(raw)
        if not tz_iana:
            tz_iana = city_to_iana(raw.replace(" ", ""))
    if not tz_iana:
        return f"Cidade «{raw}» não reconhecida. Use /tz Lisboa, /tz São Paulo ou /tz Europe/Lisbon (IANA)."
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_timezone
        db = SessionLocal()
        try:
            if set_user_timezone(db, ctx.chat_id, tz_iana):
                return f"Timezone definido: {tz_iana}. As horas dos lembretes passam a ser mostradas no teu fuso."
            return "Timezone inválido."
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
        return "Idiomas: /lang pt-pt | pt-br | es | en"
    try:
        from backend.database import SessionLocal
        from backend.user_store import set_user_language
        db = SessionLocal()
        try:
            set_user_language(db, ctx.chat_id, code)
            return f"Idioma definido: {code}."
        finally:
            db.close()
    except Exception:
        return "Erro ao gravar idioma."
    return None


async def handle_quiet(ctx: HandlerContext, content: str) -> str | None:
    """/quiet 22:00-08:00: horários silenciosos (não notificar)."""
    if not content.strip().lower().startswith("/quiet"):
        return None
    return "Horário silencioso: em breve. Ex: /quiet 22:00-08:00"


async def handle_stop(ctx: HandlerContext, content: str) -> str | None:
    """/stop: opt-out."""
    if not content.strip().lower().startswith("/stop"):
        return None
    return _reply_confirm_prompt("Quer deixar de receber mensagens? (opt-out)")


# ---------------------------------------------------------------------------
# Mimo: chamada ao LLM (Xiaomi) para formatar rever e análises
# ---------------------------------------------------------------------------

async def _call_mimo(
    ctx: HandlerContext,
    user_lang: str,
    instruction: str,
    data_text: str,
    max_tokens: int = 600,
) -> str | None:
    """Chama o Mimo (scope_provider) para gerar resposta. Retorna None se não houver provider."""
    if not ctx.scope_provider or not ctx.scope_model:
        return None
    try:
        lang_instruction = {
            "pt-PT": "Responde em português de Portugal.",
            "pt-BR": "Responde em português do Brasil.",
            "es": "Responde en español.",
            "en": "Respond in English.",
        }.get(user_lang, "Respond in the user's language.")
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
                instruction = f"O utilizador pediu para rever as últimas {len(recent)} mensagens da conversa (total na sessão: {total}). Apresenta um resumo ou lista clara e amigável, sem inventar conteúdo. Máximo 2-3 parágrafos se for muito longo."
            else:
                instruction = f"O utilizador pediu para rever todo o histórico da conversa ({len(recent)} mensagens). Apresenta um resumo ou lista clara e amigável. Se for muito longo, resume por períodos ou destaca os pontos principais."
            out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=800)
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

    # --- Rever lembretes (lista) ---
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
                    k = "agendado" if e["kind"] == "scheduled" else "entregue"
                    ts = e["created_at"].strftime("%Y-%m-%d %H:%M") if e.get("created_at") else ""
                    data_lines.append(f"[{k}] {e.get('message', '')} {ts}")
                data_text = "\n".join(data_lines)
                instruction = "O utilizador pediu para rever a lista de lembretes (agendados e entregues). Apresenta de forma clara e organizada, por data se fizer sentido."
                out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=500)
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
                instruction = "O utilizador pediu para rever o último pedido de lembrete. Indica claramente qual foi esse pedido."
            elif intent == "lembrete":
                instruction = "O utilizador pediu para rever a última lembrança que recebeu. Indica claramente qual foi."
            else:
                instruction = "O utilizador pediu para rever o último pedido e a última lembrança. Apresenta ambos de forma clara."
            out = await _call_mimo(ctx, user_lang, instruction, data_text, max_tokens=300)
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
        "O utilizador fez uma pergunta analítica sobre os dados dele (lembretes, conversa, horas, resumos). "
        "Responde de forma clara e concisa, com números quando fizer sentido (ex.: quantos lembretes, em que horas). "
        "Se pedir 'horas mais comuns', analisa as horas (coluna data/hora) e indica os horários mais frequentes. "
        "Não inventes dados; usa apenas o que está nos Dados abaixo. Se não houver dados suficientes, diz isso."
    )
    question = (content or "").strip()
    full_instruction = f"{instruction}\n\nPergunta do utilizador: «{question}»"

    out = await _call_mimo(ctx, user_lang, full_instruction, data_text, max_tokens=500)
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
    return _reply_confirm_prompt("Exportar todas as suas listas e lembretes?")


async def handle_deletar_tudo(ctx: HandlerContext, content: str) -> str | None:
    """/deletar_tudo: confirma? 1=sim 2=não."""
    import re
    if not re.match(r"^/deletar[_\s]?tudo\s*$", content.strip(), re.I):
        return None
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "deletar_tudo", {})
    return _reply_confirm_prompt("Apagar TODOS os dados (listas, lembretes, eventos)? Esta ação não tem volta.")


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
            return "Exportação cancelada."
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
                return "Exportação:\n" + "\n".join(lines) if lines else "Nada para exportar."
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao exportar: {e}"
    if action == "deletar_tudo":
        if is_confirm_no(content):
            return "Cancelado. Nenhum dado apagado."
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
                return "Todos os seus dados foram apagados."
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao apagar: {e}"
    return None


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
        handle_lembrete,
        handle_list,
        handle_feito,
        handle_filme,
        handle_add,
        handle_done,
        handle_start,
        handle_recorrente,
        handle_pendente,
        handle_hoje,
        handle_semana,
        handle_tz,
        handle_lang,
        handle_analytics,  # antes de rever: "quantos lembretes esta semana?" etc.
        handle_rever,
        handle_quiet,
        handle_stop,
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
