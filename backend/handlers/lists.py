"""Handlers for list operations: /list, /add, /feito, /remove, /pendente, ambiguous."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

from backend.handlers.utils import _normalize_nl_to_command


async def handle_list_or_events_ambiguous(ctx: "HandlerContext", content: str) -> str | None:
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


async def handle_list(ctx: "HandlerContext", content: str) -> str | None:
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
                if list_name in ("filmes", "filme", "livros", "livro", "músicas", "musica", "música", "séries", "série", "serie", "receitas", "receita") and is_absurd_request(it):
                    r = is_absurd_request(it)
                    if r:
                        return r
        elif list_name in ("filmes", "filme", "livros", "livro", "músicas", "musica", "música", "séries", "série", "serie", "receitas", "receita") and is_absurd_request(item_text):
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


async def handle_add(ctx: "HandlerContext", content: str) -> str | None:
    """/add [lista] [item]. Default lista=mercado. Aceita NL: adicione X, adiciona X."""
    content = _normalize_nl_to_command(content)

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    m = re.match(r"^/(add|añadir)\s+(.+)$", content.strip(), re.I)
    if not m:
        return None
    rest = m.group(2).strip()
    parts = rest.split(None, 1)

    _GENERIC_BEGINNINGS = {
        "os", "as", "um", "uns", "uma", "umas", "o", "a", "de", "do", "da", "em", "nas", "nos",
        "los", "las", "un", "unos", "una", "unas", "el", "la", "de", "del", "en",
        "the", "a", "an", "some", "of", "in",
    }

    if len(parts) == 1:
        list_name, item = "mercado", parts[0]
    elif parts[0].lower() in _GENERIC_BEGINNINGS:
        list_name, item = "mercado", rest
    else:
        list_name, item = parts[0], parts[1]
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    return await ctx.list_tool.execute(action="add", list_name=list_name, item_text=item)


async def handle_feito(ctx: "HandlerContext", content: str) -> str | None:
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
        item_text=intent.get("item"),
    )


async def handle_remove(ctx: "HandlerContext", content: str) -> str | None:
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
        item_text=intent.get("item"),
    )


async def handle_pendente(ctx: "HandlerContext", content: str) -> str | None:
    """/pendente: tudo aberto. Aceita NL: pendente, pendentes, tarefas pendentes."""
    content = _normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/pendente"):
        return None
    if not ctx.list_tool:
        return None
    ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
    return await ctx.list_tool.execute(action="list", list_name="")
