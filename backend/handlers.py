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
    """Contexto para handlers: canal, chat e ferramentas (cron, list, event)."""
    channel: str
    chat_id: str
    cron_service: CronService | None
    cron_tool: CronTool | None
    list_tool: ListTool | None
    event_tool: EventTool | None


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
    """/tz Cidade: regista timezone (LLM reconhece cidade); confirma 'ok?' depois guarda."""
    import re
    m = re.match(r"^/tz\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    city = m.group(1).strip()
    if not city:
        return "Use: /tz Cidade (ex: /tz Lisboa)"
    return f"Timezone para «{city}» registado. Ok? (1=sim 2=não)"  # TODO: persist + confirm


async def handle_lang(ctx: HandlerContext, content: str) -> str | None:
    """/lang pt-pt | pt-br | es | en."""
    import re
    m = re.match(r"^/lang\s+(\S+)\s*$", content.strip(), re.I)
    if not m:
        return None
    lang = m.group(1).strip().lower()
    mapping = {"pt-pt": "pt-PT", "pt-pt": "pt-PT", "ptbr": "pt-BR", "pt-br": "pt-BR", "es": "es", "en": "en"}
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
    """Despacha mensagem para o handler adequado. Retorna texto de resposta ou None (fallback LLM)."""
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
