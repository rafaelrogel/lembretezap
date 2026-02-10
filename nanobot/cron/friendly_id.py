"""Geração de IDs amigáveis para lembretes: 2–3 letras (relacionadas ao lembrete) + número. Ex: AL01, VAS02, PIC01.
Usa a lista de ~400 palavras (PT-PT, PT-BR, ES, EN) em reminder_keywords; fora do escopo, pode usar Xiaomi MIMO."""

import re
import unicodedata

from nanobot.cron.reminder_keywords import REMINDER_KEYWORDS

# Ordenar por tamanho decrescente para match mais longo primeiro
_KEYWORD_ABBR: list[tuple[str, str]] = sorted(REMINDER_KEYWORDS, key=lambda x: -len(x[0]))

# Palavras a ignorar ao extrair prefixo da primeira palavra significativa
_STOPWORDS = frozenset(
    "hora de do da das dos lembrar tomar comprar fazer beber ir para às ao no na em um uma o a e".split()
)


def _normalize(text: str) -> str:
    """Remove acentos para matching e normaliza espaços (NFC -> NFD -> remove combinantes)."""
    if not text:
        return ""
    t = (text or "").lower().strip()
    t = unicodedata.normalize("NFC", t)
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"\s+", " ", t)
    return t


def get_prefix_from_list(message: str) -> str | None:
    """
    Retorna a abreviatura (2–3 letras) se alguma palavra da lista ~400 (PT-PT, PT-BR, ES, EN) fizer match.
    Retorna None se não houver match (nesse caso o caller pode usar Xiaomi MIMO para sugerir).
    """
    norm = _normalize(message or "")
    if not norm:
        return None
    for keyword, abbr in _KEYWORD_ABBR:
        if _normalize(keyword) in norm:
            return (abbr[:3].upper()).strip()
    return None


def _get_prefix_from_message(message: str) -> str:
    """
    Deriva 2–3 letras do texto do lembrete.
    Primeiro tenta palavras-chave da lista; senão usa as primeiras letras da primeira palavra significativa.
    """
    from_list = get_prefix_from_list(message or "")
    if from_list:
        return from_list
    norm = _normalize(message or "")
    if not norm:
        return "LM"
    words = [w for w in re.split(r"\W+", norm) if len(w) >= 2 and w not in _STOPWORDS]
    if not words:
        return "LM"
    first = words[0]
    letters = []
    for c in first:
        if c.isalpha() and len(letters) < 3:
            letters.append(c.upper())
    if len(letters) < 2:
        letters = [first[:1].upper(), first[1:2].upper()] if len(first) >= 2 else [first.upper(), "0"]
    return "".join(letters[:3])


def _sanitize_prefix(prefix: str) -> str:
    """Garante prefixo 2–3 letras A–Z."""
    p = re.sub(r"[^A-Z]", "", (prefix or "").upper())[:3]
    if len(p) < 2:
        p = (p + "X")[:2] if p else "LM"
    return p


def generate_friendly_job_id(
    message: str,
    existing_ids: list[str],
    prefix_override: str | None = None,
) -> str:
    """
    Gera um ID único no formato PREFIXO + NÚMERO (ex: AL01, VAS02).
    prefix_override: se definido (ex: vindo do MIMO), usa em vez de derivar da mensagem.
    """
    prefix = _sanitize_prefix(prefix_override) if prefix_override else _sanitize_prefix(_get_prefix_from_message(message or ""))
    return _next_available_id(prefix, existing_ids)


def _next_available_id(prefix: str, existing_ids: list[str]) -> str:
    """Devolve prefix + próximo número livre (01, 02, ...)."""
    existing_set = frozenset(str(i) for i in existing_ids)
    for num in range(1, 1000):
        suffix = f"{num:02d}" if num < 100 else f"{num:03d}"
        candidate = prefix + suffix
        if candidate not in existing_set:
            return candidate
    return prefix + "99"


def generate_friendly_job_id_with_prefix(prefix: str, existing_ids: list[str]) -> str:
    """Gera ID único quando o prefixo já é conhecido (ex: sugerido pelo MIMO)."""
    return _next_available_id(_sanitize_prefix(prefix), existing_ids)
