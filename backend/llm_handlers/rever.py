"""Rever: últimas N mensagens, todo o histórico ou lembretes — com Mimo."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

from backend.llm_handlers._helpers import get_user_lang
from backend.llm_handlers.mimo import call_mimo


def _parse_rever_intent(content: str) -> tuple[str | None, int | None]:
    """Retorna (tipo, N ou None). tipo: conversa|lembretes|pedido|lembrete|rever_geral."""
    t = (content or "").strip().lower()
    if not t:
        return None, None
    m = re.search(r"rever\s+(?:últimas?\s+)?(\d+)\s*(?:mensagens?)?", t)
    if m:
        n = int(m.group(1))
        if n <= 0:
            return "conversa", 10
        if n > 500:
            n = 500
        return "conversa", n
    if re.search(r"rever\s+todo\s+(o\s+)?hist[oó]rico|hist[oó]rico\s+completo|todo\s+o\s+hist[oó]rico", t):
        return "conversa", None
    if re.search(r"rever\s+(a\s+)?conversa|rever\s+hist[oó]rico|rever\s+mensagens|hist[oó]rico\s+da\s+conversa", t):
        return "conversa", 20
    if re.search(r"rever\s+lembretes?|rever\s+lembran[cç]as|listar\s+lembretes", t):
        return "lembretes", None
    if re.search(r"rever\s+(o\s+)?pedido|qual\s+era\s+o\s+pedido|o\s+que\s+pedi", t):
        return "pedido", None
    if re.search(r"rever\s+(a\s+)?lembran[cç]a|rever\s+lembrete|qual\s+foi\s+a\s+lembran[cç]a|o\s+que\s+me\s+lembraste", t):
        return "lembrete", None
    if re.search(r"^rever\s*$", t) or t.strip() == "rever":
        return "rever_geral", None
    return None, None


async def handle_rever(ctx: "HandlerContext", content: str) -> str | None:
    """Rever conversa (10/20/50/100/todo), lembretes ou último pedido/lembrete."""
    intent, N = _parse_rever_intent(content)
    if intent is None:
        return None

    user_lang = get_user_lang(ctx.chat_id)

    from backend.locale import (
        REVER_NO_CONTEXT, REVER_NO_MESSAGES, REVER_NO_REMINDERS,
        REVER_STATUS_SCHEDULED, REVER_STATUS_SENT, REVER_STATUS_FAILED,
        REVER_NO_HISTORY, REVER_LAST_REQUEST, REVER_NO_REQUEST,
        REVER_LAST_REMINDER, REVER_NO_REMINDER, REVER_LABEL_USER, REVER_LABEL_ASSISTANT,
    )

    if intent == "conversa":
        if not ctx.session_manager:
            return REVER_NO_CONTEXT.get(user_lang, REVER_NO_CONTEXT["en"])
        try:
            key = f"{ctx.channel}:{ctx.chat_id}"
            session = ctx.session_manager.get_or_create(key)
            total = len(session.messages) if hasattr(session, "messages") else 0
            if total == 0:
                return REVER_NO_MESSAGES.get(user_lang, REVER_NO_MESSAGES["en"])
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
            out = await call_mimo(ctx, user_lang, instruction, data_text, max_tokens=560)
            if out:
                return out
            if total > len(recent):
                header = f"Últimas {len(recent)} de {total} mensagens:\n"
            else:
                header = "Mensagens:\n"
            _u = REVER_LABEL_USER.get(user_lang, REVER_LABEL_USER["en"])
            _a = REVER_LABEL_ASSISTANT.get(user_lang, REVER_LABEL_ASSISTANT["en"])
            return header + "\n".join(f"{_u if m.get('role')=='user' else _a}: {(m.get('content') or '')[:150]}" for m in recent[:30])
        except Exception as e:
            return f"Erro ao buscar conversa: {e}"

    if intent == "lembretes":
        try:
            from backend.database import SessionLocal
            from backend.reminder_history import get_reminder_history
            db = SessionLocal()
            try:
                entries = get_reminder_history(db, ctx.chat_id, kind=None, limit=50)
                if not entries:
                    return REVER_NO_REMINDERS.get(user_lang, REVER_NO_REMINDERS["en"])
                data_lines = []
                for e in entries:
                    pedido = (e.get("message") or "").strip() or "(sem texto)"
                    agendado = ""
                    if e.get("schedule_at"):
                        agendado = e["schedule_at"].strftime("%d/%m/%Y %H:%M")
                    elif e.get("created_at"):
                        agendado = e["created_at"].strftime("%d/%m/%Y %H:%M") + " (pedido)"
                    status = e.get("status") or (REVER_STATUS_SCHEDULED.get(user_lang, "scheduled") if e["kind"] == "scheduled" else REVER_STATUS_SENT.get(user_lang, "delivered"))
                    if status == "sent":
                        status = REVER_STATUS_SENT.get(user_lang, "delivered")
                        if e.get("delivered_at"):
                            agendado = agendado or e["delivered_at"].strftime("%d/%m/%Y %H:%M") + " (disparou)"
                    elif status == "failed":
                        status = REVER_STATUS_FAILED.get(user_lang, "failed")
                    elif status == "scheduled":
                        status = REVER_STATUS_SCHEDULED.get(user_lang, "scheduled")
                    data_lines.append(f"Pedido: {pedido} | Agendado para: {agendado} | Status: {status}")
                data_text = "\n".join(data_lines)
                instruction = "Lista de lembretes: Pedido | Agendado | Status. Apresenta de forma concisa, por data."
                out = await call_mimo(ctx, user_lang, instruction, data_text, max_tokens=350)
                if out:
                    return out
                return "Lembretes:\n" + "\n".join(data_lines[:20])
            finally:
                db.close()
        except Exception as e:
            return f"Erro ao buscar lembretes: {e}"

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
                return REVER_NO_HISTORY.get(user_lang, REVER_NO_HISTORY["en"])
            data_text = "\n".join(data_parts)
            if intent == "pedido":
                instruction = "Indica o último pedido de lembrete. Uma frase."
            elif intent == "lembrete":
                instruction = "Indica a última lembrança entregue. Uma frase."
            else:
                instruction = "Apresenta último pedido e última lembrança. 1-2 frases."
            out = await call_mimo(ctx, user_lang, instruction, data_text, max_tokens=210)
            if out:
                return out
            if intent == "pedido":
                return REVER_LAST_REQUEST.get(user_lang, REVER_LAST_REQUEST["en"]).format(text=last_pedido) if last_pedido else REVER_NO_REQUEST.get(user_lang, REVER_NO_REQUEST["en"])
            if intent == "lembrete":
                return REVER_LAST_REMINDER.get(user_lang, REVER_LAST_REMINDER["en"]).format(text=last_lembrete) if last_lembrete else REVER_NO_REMINDER.get(user_lang, REVER_NO_REMINDER["en"])
            return "\n".join(data_parts)
        finally:
            db.close()
    except Exception as e:
        return f"Erro ao buscar: {e}"
    return None
