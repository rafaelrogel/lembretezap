"""Livros sagrados — passagens via APIs gratuitas (só quando pedido diretamente)."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def _is_sacred_text_intent(content: str) -> bool:
    """Detecta pedido explícito de passagem da Bíblia ou Alcorão."""
    t = (content or "").strip().lower()
    if not t or len(t) < 8:
        return False
    patterns = [
        r"passagem\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"vers[ií]culo\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"(?:quero|d[aá]-?me|manda|mostra)\s+(?:uma\s+)?(?:passagem|vers[ií]culo)\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"(?:b[ií]blia|alcor[aã]o)\s*[:\-]?\s*(?:passagem|vers[ií]culo|random|aleat[oó]ria)",
        r"(?:uma\s+)?passagem\s+(?:aleat[oó]ria|random)\s+(?:da\s+)?(?:b[ií]blia|alcor[aã]o)",
        r"vers[ií]culo\s+(?:de\s+)?(?:jo[aã]o|genesis|mateus|sura)\s+\d",
    ]
    return any(re.search(p, t) for p in patterns)


def _get_user_lang(chat_id: str) -> str:
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        db = SessionLocal()
        try:
            return get_user_language(db, chat_id) or "en"
        finally:
            db.close()
    except Exception:
        return "en"


async def handle_sacred_text(ctx: "HandlerContext", content: str) -> str | None:
    """
    Passagens da Bíblia ou Alcorão. Só quando o cliente pede diretamente.
    Usa Mimo para confirmar contexto; inclui lembrete do organizador.
    """
    if not _is_sacred_text_intent(content):
        return None
    if not ctx.scope_provider or not ctx.scope_model:
        return None

    from backend.sacred_texts import (
        fetch_bible_verse, fetch_bible_random,
        fetch_quran_verse, fetch_quran_random,
        parse_bible_reference, parse_quran_reference,
        build_sacred_response,
        get_bible_translation, get_quran_edition, wants_quran_arabic,
    )
    try:
        prompt = (
            f"Mensagem do utilizador: «{content[:300]}»\n"
            "O utilizador está a pedir EXPLICITAMENTE uma passagem ou versículo da Bíblia ou do Alcorão? "
            "(não conta: 'fui à igreja', 'li o alcorão ontem', menções casuais). Responde apenas: SIM ou NAO"
        )
        r = await ctx.scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=ctx.scope_model,
            max_tokens=10,
            temperature=0,
        )
        raw = (r.content or "").strip().upper()
        if "NAO" in raw or "NÃO" in raw.upper() or raw.startswith("N"):
            return None
    except Exception:
        pass

    t = (content or "").strip().lower()
    data = None
    book = ""
    user_lang = _get_user_lang(ctx.chat_id)

    reminder = {
        "pt-PT": "Também posso ajudar com lembretes e organização quando precisares.",
        "pt-BR": "Também posso ajudar com lembretes e organização quando precisar.",
        "es": "También puedo ayudarte con recordatorios y organización cuando lo necesites.",
        "en": "I can also help with reminders and organization when you need it.",
    }.get(user_lang or "en", "I can also help with reminders and organization when you need it.")
    bible_translation = get_bible_translation(user_lang)
    quran_edition = get_quran_edition(user_lang, want_arabic=wants_quran_arabic(content))

    if "alcor" in t or "alcorão" in t or "quran" in t:
        q_ref = parse_quran_reference(content)
        if q_ref:
            data = fetch_quran_verse(q_ref[0], q_ref[1], quran_edition)
        else:
            data = fetch_quran_random(quran_edition)
        book = "quran"
    elif "bíblia" in t or "biblia" in t or "bible" in t:
        b_ref = parse_bible_reference(content)
        if b_ref:
            data = fetch_bible_verse(b_ref, bible_translation)
        else:
            data = fetch_bible_random(bible_translation)
        book = "bible"
    else:
        return None

    return build_sacred_response(book, data, reminder)
