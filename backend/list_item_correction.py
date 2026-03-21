"""Sugere correção de itens (músicas, filmes, livros, compras) com typos via Mimo."""

import unicodedata

# Listas curadas para títulos (artista - música, filme, livro)
_CURATED_LIST_NAMES = frozenset({
    "musica", "musicas", "music", "filme", "filmes", "movie", "movies",
    "livro", "livros", "book", "books", "receita", "receitas", "recipe", "recipes",
    "musicas_dance", "musicas dance", "filmes para ver", "livros para ler",
})

# Listas de compras/mercado
_GROCERY_LIST_NAMES = frozenset({
    "mercado", "compras", "shopping", "grocery", "groceries", "supermercado", "supermarket", "viveres", "comestibles"
})


def _normalize_list_name(name: str) -> str:
    """Lowercase, sem acentos e substitui espaços por underscores."""
    if not name:
        return ""
    s = (name or "").lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.replace(" ", "_")


def is_curated_list(list_name: str) -> bool:
    """True se a lista é de músicas, filmes, livros, receitas ou compras/mercado."""
    norm = _normalize_list_name(list_name or "")
    if norm in _CURATED_LIST_NAMES or norm in _GROCERY_LIST_NAMES:
        return True
    # Match prefixos: musica_, filme_, livro_, mercado_, compra_
    for prefix in ("musica", "filme", "livro", "receita", "mercado", "compra"):
        if norm.startswith(prefix + "_") or norm.startswith(prefix):
            return True
    return False


def _looks_like_title(item_text: str, list_name: str) -> bool:
    """Heurística: parece algo que precisa de correção (2+ palavras ou typo provável)."""
    if not item_text:
        return False
    # Para listas curadas (filmes/musicas), quase sempre vale tentar corrigir se > 1 palavra
    norm_ln = _normalize_list_name(list_name)
    if any(p in norm_ln for p in ("musica", "filme", "livro", "receita")):
        return len(item_text.strip().split()) >= 2
    
    # Para mercado, somos mais permissivos: até uma palavra pode ser typo (ex: "salk")
    return len(item_text.strip()) >= 3


async def suggest_correction(
    list_name: str,
    item_text: str,
    scope_provider,
    scope_model: str,
    max_len: int = 256,
) -> str | None:
    """
    Usa Mimo para sugerir correção de typos e separar itens combinados (ex: sal açúcar -> sal, açúcar).
    Retorna o texto corrigido (possivelmente com vírgulas) ou None.
    """
    if not scope_provider or not scope_model or not item_text or not item_text.strip():
        return None
    if not is_curated_list(list_name):
        return None
    if not _looks_like_title(item_text, list_name):
        return None

    try:
        norm_ln = _normalize_list_name(list_name)
        if any(p in norm_ln for p in ("musica", "filme", "livro", "receita")):
            list_type = "música" if "musica" in norm_ln else "filme" if "filme" in norm_ln else "livro" if "livro" in norm_ln else "receita"
            prompt = (
                f"User wants to add to {list_type} list: «{item_text[:300]}». "
                "Correct any spelling errors in titles. If multiple items are in the same line, separate them with commas. "
                "Reply ONLY with the corrected text. No quotes, no explanation."
            )
        else:
            prompt = (
                f"User wants to add to grocery list: «{item_text[:300]}». "
                "Correct any typos (e.g. 'salk acucar' -> 'sal, açúcar'). "
                "If multiple items are in one line or separated by spaces/newlines, separate them with commas. "
                "Reply ONLY with the corrected comma-separated items. No quotes, no explanation."
            )

        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=400, # Aumentado para suportar listas longas
            temperature=0,
        )
        out = (r.content or "").strip().strip('"\'')
        if not out or len(out) > max_len * 4: # Permitir bastantes itens
            return None
        # Só usa se for diferente
        if out.lower() != (item_text or "").lower():
            return out
    except Exception:
        pass
    return None
