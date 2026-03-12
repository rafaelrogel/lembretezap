"""Handler para busca de informações curadas (filmes, livros, músicas).

Similar ao recipe_handler, mas focado em listas de entretenimento/cultura.
Usa Perplexity para buscar informações e oferece criar/adicionar à lista.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

# Padrões que indicam pedido de busca de filmes/livros/música
_SEARCH_PATTERNS = (
    r"(?:mostre|mostra|ver|listar?|recomende|indique|quais|quais\s+s[aã]o|show|view|list|recommend|muestra|recomendar|cu[aá]les)\s+(?:os\s+|as\s+|los\s+|las\s+|the\s+)?(?:filmes?|livros?|m[uú]sicas?|pel[ií]culas?|libros?|movies?|books?|songs?)\s+(?:de|do|da|sobre|para|of|by|from|about)\s+",
    r"(?:filmes?|pel[ií]culas?|movies?)\s+(?:de|do|da|sobre|com|of|by|with|sobre)\s+",
    r"(?:livros?|libros?|books?)\s+(?:de|do|da|sobre|of|by|about)\s+",
    r"(?:m[uú]sicas?|songs?)\s+(?:de|do|da|sobre|of|by)\s+",
)

def _is_search_intent(content: str) -> bool:
    """True se a mensagem parece um pedido de busca curada."""
    t = (content or "").strip().lower()
    if not t or len(t) < 10 or t.startswith("/"):
        return False
    return any(re.search(p, t) for p in _SEARCH_PATTERNS)

def _parse_items_from_search(text: str) -> list[str]:
    """Extrai itens da resposta da Perplexity (lista numerada ou bullet)."""
    if not text or not text.strip():
        return []
    items: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) < 2:
            continue
        # Tenta casar marcadores de lista
        m = re.match(r"^[\d]+[\.\)\-]\s*(.+)$", line)
        if m:
            item = m.group(1).strip()
        elif line.startswith(("•", "◦", "-", "*")):
            item = line.lstrip("•◦-*").strip()
        else:
            # Se não tem marcador mas é curto, pode ser item sem bullet num bloco de lista.
            # Ignora se terminar em : (provável cabeçalho)
            if len(line) < 100 and not line.endswith(":"):
                item = line
            else:
                continue
        
        # Limpar negritos e aspas comuns em títulos
        item = re.sub(r"[\*\"_]", "", item).strip()
        if item and len(item) >= 2:
            items.append(item[:200])
    return items[:15]

async def handle_curated_search(ctx: HandlerContext, content: str) -> str | None:
    """
    Handler para buscas de filmes, livros, músicas.
    """
    if not _is_search_intent(content):
        return None

    from backend.recipe_handler import _get_perplexity_key, _call_perplexity_chat, _call_llm_recipe
    api_key = _get_perplexity_key()
    
    user_lang = "pt-BR"
    try:
        from backend.user_store import get_user_language
        from backend.database import SessionLocal
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
        finally:
            db.close()
    except Exception:
        pass

    # Instruções específicas para busca curada localizadas
    search_prompts = {
        "pt-BR": f"O usuário quer uma lista de itens: {content}. Responda apenas com a lista de nomes dos itens (filmes/livros/músicas), sem introduções longas. Use uma lista numerada.",
        "pt-PT": f"O utilizador quer uma lista de itens: {content}. Responde apenas com a lista de nomes dos itens (filmes/livros/músicas), sem introduções longas. Usa uma lista numerada.",
        "es": f"El usuario quiere una lista de elementos: {content}. Responde solo com la lista de nombres de los elementos (películas/libros/canciones), sin introducciones largas. Usa una lista numerada.",
        "en": f"The user wants a list of items: {content}. Respond only with the list of item names (movies/books/songs), without long introductions. Use a numbered list.",
    }
    search_prompt = search_prompts.get(user_lang, search_prompts["en"])

    result = await _call_perplexity_chat(api_key, search_prompt, user_lang)
    if not result and ctx.scope_provider:
        result = await _call_llm_recipe(ctx.scope_provider, ctx.scope_model, search_prompt, user_lang)
    
    if result:
        return _build_search_response(ctx, content, result, user_lang)

    return None

_OFFER_LIST_MSG = {
    "pt-PT": "\n\nQueres que adicione estes itens à tua lista de {list_type}?",
    "pt-BR": "\n\nQuer que eu adicione esses itens à sua lista de {list_type}?",
    "es": "\n\n¿Quieres que añada estos elementos a tu lista de {list_type}?",
    "en": "\n\nWould you like me to add these items to your {list_type} list?",
}

def _build_search_response(ctx: HandlerContext, query: str, text: str, lang: str) -> str:
    """Constrói resposta e oferece adicionar à lista."""
    items = _parse_items_from_search(text)
    
    # Determinar tipo de lista
    list_type = "filme"
    q_lower = query.lower()
    if "livro" in q_lower or "book" in q_lower or "libro" in q_lower:
        list_type = "livro"
    elif "m[uú]sica" in q_lower or "music" in q_lower or "song" in q_lower:
        list_type = "musica"

    if len(items) >= 2:
        try:
            from backend.confirmations import set_pending
            set_pending(
                ctx.channel,
                ctx.chat_id,
                "add_items_from_search",
                {"items": items, "list_name": list_type},
            )
            offer_tmpl = _OFFER_LIST_MSG.get(lang, _OFFER_LIST_MSG["pt-BR"])
            offer = offer_tmpl.format(list_type=list_type)
            return f"{text}\n{offer}"
        except Exception:
            pass
    
    return text
