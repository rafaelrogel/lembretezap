"""Handler rápido para receitas e listas de ingredientes.

1) Perplexity Chat — busca na web, ideal para receitas atualizadas.
2) Fallback DeepSeek — se Perplexity falhar, usa main_provider (DeepSeek).
3) Oferece lista de compras — quando há ingredientes, pergunta se quer criar; "sim"/"faça isso" cria a lista.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

# Padrões que indicam pedido de receita/ingredientes
_RECIPE_PATTERNS = (
    r"me\s+lembre\s+(?:a\s+)?receita",
    r"lembre\s+(?:me\s+)?(?:a\s+)?receita",
    r"fa[cç]a\s+uma\s+lista\s+de\s+ingredientes",
    r"fazer\s+uma\s+lista\s+de\s+ingredientes",
    r"lista\s+de\s+ingredientes\s+para",
    r"ingredientes\s+para\s+fazer",
    r"ingredientes\s+(?:de|da)\s+\w+",
    r"receita\s+(?:de|da)\s+",
    r"como\s+fazer\s+\w+\s+(?:de\s+)?\w*",
    r"passo\s+a\s+passo\s+para\s+fazer",
)

PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"  # sonar ou sonar-pro
PERPLEXITY_TIMEOUT = 45


_STOP_AT_PATTERNS = re.compile(
    r"^(modo\s+de\s+preparo|passos?|instru[cç][oõ]es|preparo|como\s+fazer|dire[cç][oõ]es)\s*:?\s*$",
    re.I,
)


def _parse_ingredients_from_recipe(text: str) -> list[str]:
    """
    Extrai ingredientes de texto de receita (lista numerada, bullet, etc.).
    Para antes de secções como "Modo de preparo" ou "Passos".
    """
    if not text or not text.strip():
        return []
    ingredients: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) < 2:
            continue
        if _STOP_AT_PATTERNS.match(line):
            break
        m = re.match(r"^[\d]+[\.\)\-]\s*(.+)$", line)
        if m:
            line = m.group(1).strip()
        elif line.startswith(("•", "◦", "-", "*")):
            line = line.lstrip("•◦-*").strip()
        if line and len(line) >= 2 and not _STOP_AT_PATTERNS.match(line):
            ingredients.append(line[:256])
    return ingredients[:30]


def _recipe_query_to_list_name(query: str) -> str:
    """Deriva nome da lista a partir do pedido de receita. Ex: 'receita de escondidinho' → compras_escondidinho."""
    t = (query or "").strip().lower()
    for p in (r"receita\s+(?:de|da)\s+(.+)", r"ingredientes\s+(?:de|da)\s+(.+)", r"como\s+fazer\s+(.+)", r"lista\s+de\s+ingredientes\s+para\s+(.+)"):
        m = re.search(p, t)
        if m:
            t = m.group(1).strip()
            break
    if not t:
        return "compras_receita"
    t = re.sub(r"[^\w\s\-]", "", t)
    t = re.sub(r"\s+", "_", t).strip("_")[:40]
    return f"compras_{t}" if t else "compras_receita"


def _is_recipe_intent(content: str) -> bool:
    """True se a mensagem pede receita ou lista de ingredientes."""
    t = (content or "").strip()
    if not t or len(t) < 10 or t.lower().startswith("/"):
        return False
    return any(re.search(p, t) for p in _RECIPE_PATTERNS)


def _get_perplexity_key() -> str | None:
    """Obtém a chave Perplexity do config ou env."""
    try:
        from zapista.config.loader import load_config
        config = load_config()
        if config.providers and config.providers.perplexity:
            key = (config.providers.perplexity.api_key or "").strip()
            if key:
                return key
    except Exception:
        pass
    import os
    return (os.environ.get("ZAPISTA_PROVIDERS__PERPLEXITY__API_KEY") or "").strip() or None


async def _call_perplexity_chat(api_key: str, user_message: str, lang: str = "pt-BR") -> str | None:
    """Chama a Perplexity Chat API (sonar) e retorna a resposta."""
    import httpx
    system = (
        "Responde com uma lista de ingredientes ou passos da receita. "
        "Formato: lista numerada clara. Seja conciso. Responde em português."
    )
    if "pt-PT" in (lang or ""):
        system += " Usa português de Portugal."
    try:
        async with httpx.AsyncClient(timeout=PERPLEXITY_TIMEOUT) as client:
            r = await client.post(
                PERPLEXITY_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": PERPLEXITY_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.2,
                },
            )
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        return None
    except Exception:
        return None

    choices = data.get("choices") or []
    if not choices:
        return None
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    return content if content else None


async def _call_deepseek_recipe(
    provider, model: str, user_message: str, lang: str = "pt-BR"
) -> str | None:
    """Fallback: DeepSeek para receita quando Perplexity falha."""
    if not provider or not (model or "").strip():
        return None
    system = (
        "O utilizador pede uma receita ou lista de ingredientes. Responde com ingredientes e passos. "
        "Formato: lista numerada clara. Seja conciso. Português."
    )
    if "pt-PT" in (lang or ""):
        system += " Usa português de Portugal."
    try:
        r = await provider.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            model=model,
            max_tokens=1024,
            temperature=0.3,
        )
        if r and r.content and not (r.content or "").strip().lower().startswith("error"):
            return (r.content or "").strip()
    except Exception:
        pass
    return None


async def handle_recipe(ctx: "HandlerContext", content: str) -> str | None:
    """
    Handler rápido para pedidos de receita/ingredientes.
    Usa Perplexity Chat API diretamente. Se falhar, retorna None (agent fallback).
    """
    if not _is_recipe_intent(content or ""):
        return None

    api_key = _get_perplexity_key()
    if not api_key:
        return None  # Sem chave → agent trata

    user_lang = "pt-BR"
    try:
        from backend.user_store import get_user_language
        from backend.database import SessionLocal
        db = SessionLocal()
        try:
            user_lang = get_user_language(db, ctx.chat_id) or "pt-BR"
        finally:
            db.close()
    except Exception:
        pass

    result = await _call_perplexity_chat(api_key, content.strip(), user_lang)
    if result:
        return _build_recipe_response(ctx, content.strip(), result, user_lang)

    # Fallback: DeepSeek (main_provider) — bom para receitas mesmo sem busca web
    if ctx.main_provider and (ctx.main_model or "").strip():
        result = await _call_deepseek_recipe(
            ctx.main_provider, ctx.main_model, content.strip(), user_lang
        )
        if result:
            return _build_recipe_response(ctx, content.strip(), result, user_lang)

    return None  # Agent trata (scope_provider/Mimo como último recurso)


_RECIPE_OFFER_MSG = {
    "pt-PT": "\n\nPosso criar uma lista de compras para esta receita se quiseres! 🛒",
    "pt-BR": "\n\nPosso criar uma lista de compras para esta receita se quiser! 🛒",
    "es": "\n\n¿Quieres que cree una lista de compras para esta receta? 🛒",
    "en": "\n\nI can create a shopping list for this recipe if you'd like! 🛒",
}


def _build_recipe_response(
    ctx: "HandlerContext",
    user_query: str,
    recipe_text: str,
    user_lang: str,
) -> str:
    """Constrói resposta com receita e oferta de lista de compras."""
    base = f"📋 **Lista de ingredientes**\n\n{recipe_text}"
    ingredients = _parse_ingredients_from_recipe(recipe_text)
    if len(ingredients) >= 2 and ctx.list_tool:
        try:
            from backend.confirmations import set_pending
            list_name = _recipe_query_to_list_name(user_query)
            set_pending(
                ctx.channel,
                ctx.chat_id,
                "create_shopping_list_from_recipe",
                {"ingredients": ingredients, "list_name": list_name},
            )
            offer = _RECIPE_OFFER_MSG.get(user_lang, _RECIPE_OFFER_MSG["pt-BR"])
            return base + offer
        except Exception:
            pass
    return base
