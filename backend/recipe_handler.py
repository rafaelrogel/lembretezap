"""Handler rápido para receitas e listas de ingredientes.

1) Perplexity Chat — busca na web, ideal para receitas atualizadas.
2) Fallback Mimo — se Perplexity falhar, tenta scope_provider (Mimo, mais barato).
3) Fallback DeepSeek — se Mimo também falhar, usa main_provider (DeepSeek).
4) Oferece lista de compras — quando há ingredientes, pergunta se quer criar; "sim"/"faça isso" cria a lista.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

# Padrões que indicam pedido de receita/ingredientes
_RECIPE_PATTERNS = (
    # PT
    r"me\s+lembre\s+(?:a\s+)?receita",
    r"lembre\s+(?:me\s+)?(?:a\s+)?receita",
    r"fa[cç]a\s+uma\s+lista\s+de\s+ingredientes",
    r"fazer\s+uma\s+lista\s+de\s+ingredientes",
    r"lista\s+de\s+ingredientes\s+para",
    r"ingredientes\s+para\s+fazer",
    r"ingredientes\s+(?:de|da|para)\s+\w+",
    r"receita\s+(?:de|da|para)\s+",
    r"como\s+fazer\s+\w+",
    r"passo\s+a\s+passo\s+para\s+fazer",
    # EN
    r"recipe\s+(?:for|of)\s+",
    r"how\s+to\s+make\s+\w+",
    r"ingredients\s+(?:for|of|to)\s+",
    r"ingredient\s+list\s+for",
    r"step\s+by\s+step\s+(?:for|to)\s+",
    # ES
    r"receta\s+(?:de|del|para)\s+",
    r"ingredientes\s+para\s+hacer",
    r"c[oó]mo\s+hacer\s+\w+",
    r"lista\s+de\s+ingredientes\s+para\s+hacer",
)

# Padrões para salvar receita fornecida pelo usuário
_SAVE_RECIPE_PATTERNS = (
    r"anot[ea]\s+(?:esta\s+|essa\s+)?receita",
    r"guard[ea]\s+(?:esta\s+|essa\s+)?receita",
    r"salv[ea]\s+(?:esta\s+|essa\s+)?receita",
    r"guarda\s+esta\s+receita",
    r"save\s+(?:this\s+)?recipe",
    r"guarda\s+(?:esta\s+)?receta",
)

PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"  # sonar ou sonar-pro
PERPLEXITY_TIMEOUT = 45


_STOP_AT_PATTERNS = re.compile(
    r"^(modo\s+de\s+preparo|passos?|instru[cç][oõ]es|preparo|como\s+fazer|dire[cç][oõ]es"
    r"|instructions?|directions?|preparation|steps|method|how\s+to\s+make"
    r"|preparaci[oó]n|instrucciones|pasos)\s*:?\s*$",
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
    found_start = False
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) < 2:
            continue
        if _STOP_AT_PATTERNS.match(line):
            break
        
        # Só começar a extrair se vir um marcador de lista (número ou bullet)
        m = re.match(r"^[\d]+[\.\)\-]\s*(.+)$", line)
        if m:
            found_start = True
            line = m.group(1).strip()
        elif line.startswith(("•", "◦", "-", "*")):
            found_start = True
            line = line.lstrip("•◦-*").strip()
        elif found_start:
            # Se já começamos e a linha não tem marcador, mas é texto curto, pode ser continuação ou item sem bullet
            pass
        else:
            continue

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
    return any(re.search(p, t, re.I) for p in _RECIPE_PATTERNS)


def _is_save_recipe_intent(content: str) -> bool:
    """True se a mensagem parece ser o usuário fornecendo uma receita para guardar."""
    t = (content or "").strip()
    if not t or len(t) < 15 or t.lower().startswith("/"):
        return False
    # Deve conter um dos padrões de "anota/guarda" E "receita"
    return any(re.search(p, t, re.I) for p in _SAVE_RECIPE_PATTERNS)


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
    # Instruções de sistema localizadas
    instructions = {
        "pt-BR": "Responda com uma lista de ingredientes e passos da receita. Formato: lista numerada clara. Seja conciso. Responda em português do Brasil.",
        "pt-PT": "Responda com uma lista de ingredientes e passos da receita. Formato: lista numerada clara. Seja conciso. Responda em português de Portugal.",
        "es": "Responde con una lista de ingredientes y pasos de la receta. Formato: lista numerada clara. Sé conciso. Responde en español.",
        "en": "Respond with a list of ingredients and recipe steps. Format: clear numbered list. Be concise. Respond in English.",
    }
    system = instructions.get(lang, instructions["en"])
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


async def _call_llm_recipe(
    provider, model: str, user_message: str, lang: str = "pt-BR"
) -> str | None:
    """Chama qualquer LLM (Mimo ou DeepSeek) para gerar receita."""
    if not provider or not (model or "").strip():
        return None
    # Instruções de sistema localizadas
    instructions = {
        "pt-BR": "O utilizador pede uma receita ou lista de ingredientes. Responda com ingredientes e passos. Formato: lista numerada clara. Seja conciso. Português do Brasil.",
        "pt-PT": "O utilizador pede uma receita ou lista de ingredientes. Responda com ingredientes e passos. Formato: lista numerada clara. Seja conciso. Português de Portugal.",
        "es": "El usuario solicita una receta o lista de ingredientes. Responde con ingredientes y pasos. Formato: lista numerada clara. Sé conciso. Español.",
        "en": "User asks for a recipe or list of ingredients. Respond with ingredients and steps. Format: clear numbered list. Be concise. English.",
    }
    system = instructions.get(lang, instructions["en"])
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
    Handler para pedidos de receita (busca) OU salvar receita fornecida.
    """
    content_strip = (content or "").strip()
    
    # 1. Caso: Salvar receita fornecida pelo usuário
    if _is_save_recipe_intent(content_strip):
        return await _handle_save_provided_recipe(ctx, content_strip)

    # 2. Caso: Buscar receita na web
    if not _is_recipe_intent(content_strip):
        return None

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

    result = await _call_perplexity_chat(api_key, content_strip, user_lang)
    if result:
        return _build_recipe_response(ctx, content_strip, result, user_lang)

    # Fallback 1: Mimo (scope_provider) — mais barato
    if ctx.scope_provider and (ctx.scope_model or "").strip():
        result = await _call_llm_recipe(
            ctx.scope_provider, ctx.scope_model, content_strip, user_lang
        )
        if result:
            return _build_recipe_response(ctx, content_strip, result, user_lang)

    # Fallback 2: DeepSeek (main_provider)
    if ctx.main_provider and (ctx.main_model or "").strip():
        result = await _call_llm_recipe(
            ctx.main_provider, ctx.main_model, content_strip, user_lang
        )
        if result:
            return _build_recipe_response(ctx, content_strip, result, user_lang)

    return None  # Agent trata


async def _handle_save_provided_recipe(ctx: "HandlerContext", content: str) -> str | None:
    """Estrutura e guarda uma receita que o próprio usuário enviou."""
    if not ctx.scope_provider or not ctx.scope_model:
        return None # Deixa cair no handler comum de lista (sem organização)

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

    prompt = (
        "O usuário enviou uma receita de forma desestruturada. Extraia o Título, "
        "a lista de Ingredientes e o Modo de Preparo. Formate como um bloco de texto "
        "claro e organizado. Responda APENAS com a receita formatada.\n\n"
        f"Texto do usuário: {content}"
    )
    if user_lang == "en":
        prompt = (
            "The user sent a recipe in an unstructured way. Extract the Title, "
            "the list of Ingredients, and the Preparation steps. Format it as a "
            "clear and organized text block. Respond ONLY with the formatted recipe.\n\n"
            f"User text: {content}"
        )
    elif user_lang == "es":
        prompt = (
            "El usuario envió una receta de forma desestructurada. Extraiga el Título, "
            "la lista de Ingredientes y el Modo de Preparo. Formatee como un bloque de texto "
            "claro y organizado. Responda SOLAMENTE con la receta formateada.\n\n"
            f"Texto del usuario: {content}"
        )

    formatted_recipe = await ctx.scope_provider.chat(
        messages=[{"role": "user", "content": prompt}],
        model=ctx.scope_model,
        max_tokens=1024,
        temperature=0.2,
    )
    recipe_text = (formatted_recipe.content or "").strip()
    if not recipe_text or recipe_text.lower().startswith("error"):
        return None

    # Salva na lista 'receitas'
    if ctx.list_tool:
        ctx.list_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)
        # Bypass fragmentation by passing as-is (list_tool _add uses _split_items, 
        # but _split_items won't split if any part is > 120 chars, and the formatted recipe will definitely have long parts)
        await ctx.list_tool.execute(action="add", list_name="receitas", item_text=recipe_text, no_split=True)
        
        # Oferece lista de compras
        return _build_recipe_response(ctx, content, recipe_text, user_lang)
    
    return recipe_text


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
