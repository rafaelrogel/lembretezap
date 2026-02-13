"""«Sobre o que estávamos falando?» — resumo da conversa com Mimo."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

from backend.llm_handlers._helpers import get_user_lang
from backend.llm_handlers.mimo import call_mimo


def _is_resumo_conversa_intent(content: str) -> bool:
    """Detecta pedidos explícitos de resumo da conversa."""
    t = (content or "").strip().lower()
    if not t or len(t) < 8:
        return False
    patterns = [
        r"sobre\s+o\s+que\s+(est[aá]vamos|estamos)\s+falando",
        r"o\s+que\s+fal[aá]mos",
        r"o\s+que\s+(estava|estava[va]mos)\s+(a\s+)?falando",
        r"resumo\s+da\s+conversa",
        r"resumir\s+o\s+que\s+falamos",
        r"do\s+que\s+falamos",
        r"o\s+que\s+discutimos",
        r"o\s+que\s+conversamos",
        r"lembra\s+(do\s+que|o\s+que)\s+falamos",
        r"em\s+que\s+ponto\s+paramos",
        r"onde\s+paramos",
        r"retomar\s+(de\s+onde|a\s+conversa)",
    ]
    return any(re.search(p, t) for p in patterns)


async def handle_resumo_conversa(ctx: "HandlerContext", content: str) -> str | None:
    """«Sobre o que estávamos falando?», «resumo da conversa» — usa sessão + Mimo."""
    if not _is_resumo_conversa_intent(content):
        return None
    if not ctx.session_manager or not ctx.scope_provider or not ctx.scope_model:
        return None

    session_key = f"{ctx.channel}:{ctx.chat_id}"
    session = ctx.session_manager.get_or_create(session_key)
    total = len(session.messages) if hasattr(session, "messages") else 0
    if total == 0:
        user_lang = get_user_lang(ctx.chat_id)
        lang_msg = {
            "pt-PT": "Ainda não há mensagens nesta conversa.",
            "pt-BR": "Ainda não há mensagens nesta conversa.",
            "es": "Aún no hay mensajes en esta conversación.",
            "en": "No messages in this conversation yet.",
        }
        return lang_msg.get(user_lang, lang_msg["pt-BR"])

    recent = session.messages[-30:] if len(session.messages) > 30 else list(session.messages)
    lines = []
    for m in recent:
        role = m.get("role", "")
        cont = (m.get("content") or "").strip()
        label = "Utilizador" if role == "user" else "Assistente"
        lines.append(f"[{label}] {cont}")
    data_text = "\n".join(lines) if lines else ""

    user_lang = get_user_lang(ctx.chat_id)
    instruction = (
        "O utilizador quer um resumo do que estava a ser falado na conversa. "
        "Resume as mensagens seguintes em 2-4 frases curtas. Foco no essencial: lembretes, listas, decisões, pedidos. Sem inventar."
    )
    out = await call_mimo(ctx, user_lang, instruction, data_text, max_tokens=280)
    if out:
        return out
    return "Últimos temas:\n" + "\n".join(lines[:8]) if lines else "Nada a resumir."
