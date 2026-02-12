"""Sugere correção de itens (músicas, filmes, livros) com typos via Mimo."""

# Listas onde faz sentido corrigir títulos (artista - música, filme, livro)
_CURATED_LIST_NAMES = frozenset({
    "musica", "musicas", "music", "filme", "filmes", "movie", "movies",
    "livro", "livros", "book", "books", "receita", "receitas", "recipe", "recipes",
    "musicas_dance", "musicas dance", "filmes para ver", "livros para ler",
})


def _normalize_list_name(name: str) -> str:
    """Lowercase, sem acentos para match."""
    if not name:
        return ""
    import unicodedata
    s = (name or "").lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.replace(" ", "_")


def is_curated_list(list_name: str) -> bool:
    """True se a lista é de músicas, filmes, livros ou receitas."""
    norm = _normalize_list_name(list_name or "")
    if norm in _CURATED_LIST_NAMES:
        return True
    # Match prefixos: musica_, filme_, livro_
    for prefix in ("musica", "filme", "livro", "receita"):
        if norm.startswith(prefix + "_") or norm.startswith(prefix):
            return True
    return False


def _looks_like_title(item_text: str) -> bool:
    """Heurística: parece um título (2+ palavras, não só 'leite')."""
    if not item_text or len(item_text.strip()) < 5:
        return False
    words = (item_text or "").strip().split()
    return len(words) >= 2


async def suggest_correction(
    list_name: str,
    item_text: str,
    scope_provider,
    scope_model: str,
    max_len: int = 256,
) -> str | None:
    """
    Usa Mimo para sugerir correção de possível typo (ex: Corone rythym of the nai → Corona - Rhythm of the Night).
    Retorna o texto corrigido ou None se não aplicar/indisponível.
    """
    if not scope_provider or not scope_model or not item_text or not item_text.strip():
        return None
    if not is_curated_list(list_name):
        return None
    if not _looks_like_title(item_text):
        return None
    try:
        list_type = "música" if "music" in _normalize_list_name(list_name) or "musica" in _normalize_list_name(list_name) else "filme" if "filme" in _normalize_list_name(list_name) else "livro" if "livro" in _normalize_list_name(list_name) else "receita" if "receita" in _normalize_list_name(list_name) else "item"
        prompt = (
            f"User wants to add to {list_type} list: «{item_text[:150]}». "
            "If there are spelling errors in artist/song/movie/book title, reply with ONLY the corrected form (e.g. 'Artist - Song Title'). "
            "Otherwise reply with the exact same text. One line, no explanation, no quotes."
        )
        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=80,
            temperature=0,
        )
        out = (r.content or "").strip().strip('"\'')
        if not out or len(out) > max_len:
            return None
        # Só usa se for diferente (evita chamadas inúteis retornando igual)
        if out.lower() != (item_text or "").lower():
            return out
    except Exception:
        pass
    return None
