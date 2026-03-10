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

    try:
        from backend.guardrails import is_complex_request
        if is_complex_request(content):
            return None
    except Exception:
        pass

    parts = []

    if ctx.cron_tool:
        ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
        cron_out = await ctx.cron_tool.execute(action="list")
        if "Nenhum lembrete" not in cron_out:
            parts.append(cron_out)
        else:
            parts.append("📅 **Lembretes:** Nenhum agendado.")

    # Mostrar também eventos da Agenda
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_or_create_user, get_user_timezone
        from backend.models_db import Event
        from zoneinfo import ZoneInfo
        
        db = SessionLocal()
        try:
            user = get_or_create_user(db, ctx.chat_id, phone=ctx.phone_for_locale)
            tz_iana = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale) or "UTC"
            tz = ZoneInfo(tz_iana)
            
            events = db.query(Event).filter(
                Event.user_id == user.id,
                Event.tipo == "evento",
                Event.deleted == False
            ).all()
            
            if events:
                lines = ["📆 **Eventos na Agenda:**"]
                for ev in events:
                    nome = ev.payload.get("nome", "Evento Desconhecido").strip()
                    if ev.data_at:
                        ev_local = ev.data_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                        dt_str = ev_local.strftime("%d/%m %H:%M")
                    else:
                        dt_str = "S/ Data"
                    lines.append(f"• {dt_str} — {nome}")
                parts.append("\n".join(lines))
        finally:
            db.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

    # As listas (filme, livro, música) agora são tratadas pelo ListTool
    # o LLM decidir mostrar as listas.
    
    if not parts:
        from backend.locale import UNIFICADO_EMPTY
        from backend.user_store import get_user_language
        lang = get_user_language(ctx.db if hasattr(ctx, "db") else None, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        return UNIFICADO_EMPTY.get(lang, UNIFICADO_EMPTY["en"])
    return "\n\n".join(parts)
