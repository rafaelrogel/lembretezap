"""Visão unificada: lembretes (cron) + eventos (filme, livro, etc.)."""

import re

from backend.handler_context import HandlerContext


def _is_eventos_unificado_intent(content: str) -> bool:
    """Detecta pedidos de visão unificada: eventos + lembretes."""
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

    if ctx.cron_tool:
        ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)
        cron_out = await ctx.cron_tool.execute(action="list")
        if "Nenhum lembrete" not in cron_out:
            parts.append(cron_out)
        else:
            parts.append("📅 **Lembretes:** Nenhum agendado.")

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
