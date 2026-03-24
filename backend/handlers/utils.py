"""Shared helpers and general-purpose handlers (/start, /help, /stop)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


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


def _normalize_nl_to_command(content: str) -> str:
    """Reexport para uso neste módulo; lógica em backend.command_nl."""
    from backend.command_nl import normalize_nl_to_command
    return normalize_nl_to_command(content)


async def handle_start(ctx: "HandlerContext", content: str) -> str | None:
    """/start: opt-in, setup timezone/idioma. Aceita NL: começar, início, iniciar."""
    content = _normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/start"):
        return None
    return (
        "👋 Olá! Sou o Zappelin 🛳️: lembretes, listas e eventos.\n\n"
        "📌 Comandos: /lembrete, /list (filmes, livros, músicas, séries, receitas, notas, mercado…).\n"
        "🌍 Timezone: /tz Cidade  |  Idioma: /lang pt-pt ou pt-br ou es ou en.\n\n"
        "Digite /help para ver tudo — ou escreve/envia áudio para conversar. 😊"
    )


async def handle_help(ctx: "HandlerContext", content: str) -> str | list[str] | None:
    """/help, /ajuda: lista completa de comandos."""
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
        pass

    main = build_help(user_lang)
    commands_msg = build_help_commands_list(user_lang)
    return [main, commands_msg]


async def handle_stop(ctx: "HandlerContext", content: str) -> str | None:
    """/stop: opt-out. Aceita NL: parar, pausar, stop."""
    content = _normalize_nl_to_command(content)
    if not content.strip().lower().startswith("/stop"):
        return None
    
    from backend.locale import STOP_CONFIRM_PROMPT, resolve_response_language
    from backend.user_store import get_user_language
    from backend.database import SessionLocal
    
    lang = "pt-BR"
    db = SessionLocal()
    try:
        lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
    finally:
        db.close()
        
    prompt = STOP_CONFIRM_PROMPT.get(lang, STOP_CONFIRM_PROMPT["en"])
    from backend.confirmations import set_pending
    set_pending(ctx.channel, ctx.chat_id, "confirm_stop", {})
    
    from backend.handler_context import _reply_confirm_prompt
    return _reply_confirm_prompt(prompt)


async def handle_resume(ctx: "HandlerContext", content: str) -> str | None:
    """/resume, /start: opt-in. Aceita NL: continuar, retomar, voltar."""
    from backend.command_nl import normalize_nl_to_command
    content = normalize_nl_to_command(content)
    c = content.strip().lower()
    
    # /resume ou /start (se já estiver pausado)
    if not (c.startswith("/resume") or c.startswith("/start") or c.startswith("/continuar") or c.startswith("/retomar")):
        return None
        
    from backend.database import SessionLocal
    from backend.user_store import get_user_language, get_or_create_user
    from backend.locale import RESUME_SUCCESS_MSG, RESUME_ALREADY_ACTIVE_MSG, resolve_response_language
    
    db = SessionLocal()
    try:
        user = get_or_create_user(db, ctx.chat_id)
        lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        lang = resolve_response_language(lang, ctx.chat_id, ctx.phone_for_locale)
        
        if getattr(user, "is_paused", False):
            user.is_paused = False
            db.commit()
            return RESUME_SUCCESS_MSG.get(lang, RESUME_SUCCESS_MSG["en"])
        else:
            # Se for /resume explícito, avisar que já está ativo. Se for /start, deixar seguir para o boas-vindas padrão?
            # Se for /start, o router vai tentar handle_start primeiro.
            if c.startswith("/resume") or c.startswith("/continuar") or c.startswith("/retomar"):
                return RESUME_ALREADY_ACTIVE_MSG.get(lang, RESUME_ALREADY_ACTIVE_MSG["en"])
            return None # Deixar handle_start processar se for /start
    finally:
        db.close()
