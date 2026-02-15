"""
Mensagem extra (empatia ou positiva) para lembretes/eventos.
Prioridade: primeiro tenta empatia (situações difíceis); se não bater, tenta positiva (estudos, encontros, etc.).
"""

from backend.empathy_positive_data import (
    EMPATHY_CATEGORIES,
    POSITIVE_CATEGORIES,
)

_SUPPORTED = ("pt-BR", "pt-PT", "es", "en")


def get_extra_message_for_reminder(content: str, user_lang: str) -> str:
    """
    Dado o texto do lembrete ou evento (ex.: "consulta oncologia segunda", "jantar com amigos"),
    devolve uma mensagem extra empática ou positiva, ou string vazia.
    user_lang: pt-BR | pt-PT | es | en
    """
    if not content or not content.strip():
        return ""
    lang = user_lang if user_lang in _SUPPORTED else "en"
    text = content.strip().lower()

    for cat in EMPATHY_CATEGORIES:
        kws = cat["keywords"].get(lang, cat["keywords"].get("en", []))
        for kw in kws:
            if kw and kw.lower() in text:
                msg = cat["messages"].get(lang) or cat["messages"].get("en", "")
                if msg:
                    return msg

    for cat in POSITIVE_CATEGORIES:
        kws = cat["keywords"].get(lang, cat["keywords"].get("en", []))
        for kw in kws:
            if kw and kw.lower() in text:
                msg = cat["messages"].get(lang) or cat["messages"].get("en", "")
                if msg:
                    return msg

    return ""
