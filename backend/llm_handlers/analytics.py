"""Perguntas analíticas (quantos lembretes, horas comuns, resumos) — Mimo."""

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

from backend.llm_handlers._helpers import get_user_lang
from backend.llm_handlers.mimo import call_mimo


def _is_analytics_intent(content: str) -> bool:
    """Detecta se a mensagem é uma pergunta analítica sobre histórico/lembretes."""
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
        r"resumir\s+(a\s+)?conversa",
        r"analisar\s+(os\s+)?lembretes?",
    ]
    return any(re.search(p, t) for p in patterns)


def is_analytical_message(content: str) -> bool:
    """True se a mensagem for analítica. Usado no agent loop para escolher Mimo."""
    return _is_analytics_intent(content)


async def handle_analytics(ctx: "HandlerContext", content: str) -> str | None:
    """Perguntas analíticas sobre histórico (quantos lembretes, horas comuns, resumos)."""
    if not _is_analytics_intent(content):
        return None

    user_lang = get_user_lang(ctx.chat_id)

    from backend.database import SessionLocal
    from backend.reminder_history import get_reminder_history

    tz_iana = "UTC"
    db = SessionLocal()
    try:
        from backend.user_store import get_user_timezone
        from backend.timezone import phone_to_default_timezone
        from zoneinfo import ZoneInfo
        from zapista.clock_drift import get_effective_time
        
        tz_iana = get_user_timezone(db, ctx.chat_id) or phone_to_default_timezone(ctx.chat_id) or "UTC"
        z = ZoneInfo(tz_iana)
        now_ts = get_effective_time()
        now_local = datetime.fromtimestamp(now_ts, tz=z)
        
        now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        week_start = now - timedelta(days=now.weekday())
        entries = get_reminder_history(db, ctx.chat_id, kind=None, limit=100, since=week_start)
        week_ago = now - timedelta(days=7)
        entries_7d = get_reminder_history(db, ctx.chat_id, kind=None, limit=100, since=week_ago)
    finally:
        db.close()

    def _format_entries(ents: list) -> str:
        lines = []
        for e in ents:
            k = "agendado" if e["kind"] == "scheduled" else "entregue"
            created = e.get("created_at")
            if created and hasattr(created, "strftime"):
                # Mostrar no fuso do utilizador na análise
                try:
                    ts_local = created.replace(tzinfo=timezone.utc).astimezone(z)
                    ts = ts_local.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    ts = created.strftime("%Y-%m-%d %H:%M")
            else:
                ts = ""
            lines.append(f"{k}\t{ts}\t{e.get('message', '')}")
        return "\n".join(lines)

    data_week = _format_entries(entries)
    data_7d = _format_entries(entries_7d)
    total_week = len(entries)
    total_7d = len(entries_7d)

    msg_count = 0
    if ctx.session_manager:
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            msg_count = len(session.messages) if hasattr(session, "messages") else 0
        except Exception:
            pass

    data_text = (
        f"Current Time (User): {now_local.strftime('%Y-%m-%d %H:%M (%A)')}\n"
        f"Timezone: {tz_iana}\n\n"
        f"Lembretes desde início da semana (UTC reference): {total_week} entradas.\n"
        f"Lembretes últimos 7 dias: {total_7d} entradas.\n"
        f"Total de mensagens na conversa (sessão): {msg_count}.\n\n"
        "Lista de lembretes (tipo, data/hora local, mensagem):\n"
        f"{data_7d or '(nenhum)'}"
    )

    instruction = (
        "Pergunta analítica sobre lembretes/dados. Resposta curta (1-3 frases). Com números se pedido. Sem inventar."
    )
    question = (content or "").strip()
    full_instruction = f"{instruction}\n\nPergunta do utilizador: «{question}»"

    out = await call_mimo(ctx, user_lang, full_instruction, data_text, max_tokens=350)
    if out:
        return out
    if total_7d == 0:
        return "Ainda não há lembretes registados neste período para analisar."
    return f"Esta semana: {total_week} lembretes. Últimos 7 dias: {total_7d} lembretes. (Resposta detalhada requer Mimo.)"
