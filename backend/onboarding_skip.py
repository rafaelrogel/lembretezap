"""
Detecta recusa, skip ou resposta inadequada no onboarding.
Quando o cliente não responde corretamente, permitimos avançar com valores por defeito.
"""

import re


# Respostas que indicam recusa/skip (não quero, tira isso, etc.)
_REFUSAL_SKIP_PATTERNS = (
    r"^(n[aã]o|no)\s*$",
    r"^(n[aã]o\s+quero|n[aã]o\s+quero\s+saber)",
    r"^(nenhum|nothing|nada)\s*$",
    r"^(skip|pula|saltar|pular)\s*$",
    r"^(tira|remove|tira\s+isso|tira\s+esta)\b",
    r"^(para|stop|basta)\s*$",
    r"^(n[aã]o\s+me\s+importa|n[aã]o\s+quero\s+dizer)",
    r"^(whatever|tanto\s+faz)",
    r"^(fds|foda|porra)\b",
    r"^(treta|chato|chata)\b",
    r"^(que\s+cena\s+chata|que\s+chato)\b",
    r"^(amor\s+de\s+deus|por\s+amor)\b",
    r"^(ent[aã]o)\s*\.*$",  # "Então", "Então..." — impaciência, avançar
    r"^(noooo+|n[aã]o+)\s*$",
    r"https?://",  # URLs (links) não são resposta válida
)
_REFUSAL_RE = re.compile("|".join(_REFUSAL_SKIP_PATTERNS), re.I)


# Palavras que sugerem reclamação (não resposta à pergunta)
_COMPLAINT_KEYWORDS = (
    "chato", "chata", "treta", "tretas", "chato demais", "aborrecido",
    "ridículo", "ridiculo", "porcaria", "merda", "tirar", "tira",
)

# Respostas ofensivas, inapropriadas ou claramente irrelevantes
_INAPPROPRIATE_PATTERNS = (
    r"\b(puta|foda|caralho|merda|porra|cu)\b",
    r"\b(fuck|shit|damn)\b",
    r"\b(odeio|hate)\b.*\b(isto|isso|you|tu)\b",
    r"^(ah|eh|uh|hmm)\s*\.*$",  # Somente preenchimento
    r"^[^\w\s]{5,}$",  # Apenas emojis/símbolos
)
_INAPPROPRIATE_RE = re.compile("|".join(_INAPPROPRIATE_PATTERNS), re.I)


def is_onboarding_refusal_or_skip(content: str | None) -> bool:
    """
    True se a mensagem parece recusa/skip/complaint em vez de resposta válida.
    Permite avançar com valor por defeito em vez de repetir a pergunta.
    """
    if not content or not content.strip():
        return False
    t = content.strip().lower()
    if len(t) > 300:  # Resposta muito longa (ex.: link, parágrafo) provavelmente off-topic
        return True
    if _REFUSAL_RE.search(t):
        return True
    if any(kw in t for kw in _COMPLAINT_KEYWORDS):
        return True
    return False


def looks_like_url_or_off_topic(content: str | None) -> bool:
    """True se conteúdo é URL, link ou claramente off-topic."""
    if not content or not content.strip():
        return False
    t = content.strip()
    if "http://" in t or "https://" in t or "www." in t:
        return True
    if len(t) > 200 and " " not in t[:50]:  # Possível link sem espaços
        return True
    return False


def is_likely_not_city(content: str | None) -> bool:
    """
    True se o conteúdo provavelmente não é uma cidade.
    Usado para não guardar "Nenhum", "Não", etc. como cidade.
    """
    if not content or not content.strip():
        return True
    t = content.strip().lower()
    not_cities = ("nenhum", "não", "nao", "no", "nada", "nothing", "skip", "sim", "yes")
    if t in not_cities or t in ("não.", "nao.", "no."):
        return True
    if is_onboarding_refusal_or_skip(content):
        return True
    if looks_like_url_or_off_topic(content):
        return True
    return False


def is_inappropriate_or_invalid_onboarding_response(content: str | None) -> bool:
    """
    True se a resposta parece ofensiva, irrelevante ou inapropriada.
    Nestes casos, não interpretar como escolha; repetir a pergunta ou oferecer pular.
    """
    if not content or not content.strip():
        return True
    t = content.strip()
    if len(t) > 200:  # Resposta muito longa (ex.: colar texto)
        return True
    if _INAPPROPRIATE_RE.search(t):
        return True
    if is_onboarding_refusal_or_skip(content):
        return False  # Skip/recusa é tratado separadamente
    if looks_like_url_or_off_topic(content):
        return True
    return False


def is_likely_valid_name(content: str | None) -> bool:
    """
    True se o conteúdo parece um nome válido (não recusa, não URL).
    Nomes típicos: 1-3 palavras, sem caracteres estranhos.
    """
    if not content or not content.strip():
        return False
    t = content.strip()
    if len(t) > 60:  # Muito longo para nome
        return False
    if is_onboarding_refusal_or_skip(content):
        return False
    if looks_like_url_or_off_topic(content):
        return False
    return True
