"""Visão unificada: lembretes (cron) + listas (filmes, livros, músicas, etc.).
Nota: Agenda e eventos são sinónimos (compromissos com data/hora). Listas = filmes, livros, músicas, notas, sites, to-dos, etc."""

import re

from backend.handler_context import HandlerContext


def _is_eventos_unificado_intent(content: str) -> bool:
    """Detecta pedidos de visão unificada: lembretes + listas/agenda."""
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
    """Visão unificada: lembretes (cron) + listas (filmes, livros, músicas, etc.)."""
    if not _is_eventos_unificado_intent(content):
        return None

    parts = []

    if ctx.cron_tool:
        ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
        cron_out = await ctx.cron_tool.execute(action="list")
        if "Nenhum lembrete" not in cron_out:
            parts.append(cron_out)
        else:
            parts.append("📅 **Lembretes:** Nenhum agendado.")

    # As listas (filme, livro, música, agenda) agora são tratadas pelo ListTool
    # e já aparecem na listagem de listas se o utilizador pedir para listar ou se
    # o LLM decidir mostrar as listas.
    
    if not parts:
        from backend.locale import UNIFICADO_EMPTY
        from backend.user_store import get_user_language
        lang = get_user_language(ctx.db if hasattr(ctx, "db") else None, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        return UNIFICADO_EMPTY.get(lang, UNIFICADO_EMPTY["en"])
    return "\n\n".join(parts)
