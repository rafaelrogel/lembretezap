"""Pedido de contacto com atendimento ao cliente."""

from backend.handler_context import HandlerContext


async def handle_atendimento_request(ctx: HandlerContext, content: str) -> str | None:
    """Quando o cliente pede falar com atendimento: registar em painpoints e responder com contacto + mensagem empática (Mimo primeiro)."""
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
    return await build_atendimento_response(
        user_lang,
        provider=ctx.main_provider,
        model=ctx.main_model or "",
        scope_provider=ctx.scope_provider,
        scope_model=ctx.scope_model,
    )

