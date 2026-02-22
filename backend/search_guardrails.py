"""Guardrails para busca na web (Perplexity): whitelist de escopo e bloqueio de pedidos absurdos."""

import re
from typing import Any

# Whitelist: tipos de busca que enriquecem listas/eventos no escopo (organização)
# Aceita buscas para: músicas, filmes, livros, receitas, sugestões de conteúdo
SEARCH_WHITELIST_PATTERNS = (
    # Músicas
    r"\b(melhores?\s+)?(m[uú]sicas?|songs?|music)\b",
    r"\b(dance|pop|rock|sertanejo|funk|forr[oó])\b",
    # Filmes
    r"\b(melhores?\s+)?(filmes?|movies?|film)\b",
    # Livros — inclui "livros de X", "melhores livros de Jorge Amado"
    r"\b(melhores?\s+)?(livros?|books?)\b",
    r"\b(livros?\s+de\s+\w+)\b",
    r"\b(obras?\s+de\s+\w+)\b",
    # Receitas
    r"\b(melhores?\s+)?(receitas?|recipes?)\b",
    r"\b(receitas?\s+de\s+\w+)\b",
    # Listas e rankings
    r"\b(lista\s+de|lista\s+das?\s+melhores?|top\s+\d+)\b",
    r"\b(melhores?\s+\w+\s+de\s+\w+)\b",  # "melhores livros de autor"
    # Eventos
    r"\b(convidados?|invitations?|convidar)\b",
    r"\b(festas?|casamento|party|event)\b",
    r"\b(\d{4})\b",  # anos (ex: 2023, 2025)
    # Organização e Localização
    r"\b(organiza[çc][aã]o|organizar|organize)\b",
    r"\b(sugest[oõ]es?|suggestions?|sugira|sugira-me)\b",
    r"\b(adicionar|adiciona|add)\s+(à|a|na)\s+lista\b",
    r"\b(cidade|city|town|village)\b",
    r"\b(fuso\s+hor[aá]rio|timezone|fuso|iana|utc)\b",
    r"\b(onde\s+fica|localiza[çc][aã]o|location)\b",
)

# Bloqueios: injeção, URLs, pedidos fora do escopo
_SEARCH_BLOCK_PATTERNS = (
    re.compile(r"https?://", re.I),
    re.compile(r"\.(com|org|net|io)\b", re.I),
    re.compile(r"site:\s*\S+", re.I),
    re.compile(r"ignore\s+(all\s+)?(instructions?|instruções)", re.I),
    re.compile(r"prompt\s+injection|jailbreak", re.I),
    re.compile(r"<\s*script|javascript:", re.I),
)
# Máximo de caracteres na query
MAX_QUERY_LEN = 200


def is_search_reasonable(query: str) -> bool:
    """
    True se a query está na whitelist (relacionada a listas, músicas, filmes, receitas, etc.).
    """
    if not query or not (q := query.strip()) or len(q) > MAX_QUERY_LEN:
        return False
    ql = q.lower()
    return any(re.search(p, ql, re.I) for p in SEARCH_WHITELIST_PATTERNS)


def is_absurd_search(query: str) -> str | None:
    """
    Retorna mensagem de erro se a busca é absurda/perigosa; None se ok.
    """
    if not query or not query.strip():
        return "Query vazia."
    q = (query or "").strip()
    if len(q) > MAX_QUERY_LEN:
        return f"Query muito longa (máx. {MAX_QUERY_LEN} caracteres)."
    for pat in _SEARCH_BLOCK_PATTERNS:
        if pat.search(q):
            return "Tipo de busca não permitido."
    return None
