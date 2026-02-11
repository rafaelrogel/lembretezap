"""
Formatação de lembretes na entrega: quando o lembrete é "mandar mensagem para X: texto",
o texto deve vir isolado para o cliente poder encaminhar com facilidade.
"""

import re
from typing import Literal

LangCode = Literal["pt-PT", "pt-BR", "es", "en"]

# Padrões que indicam "lembrete para mandar/enviar uma mensagem a alguém" (pt, es, en)
_SEND_MESSAGE_PATTERNS = [
    # "mandar a seguinte mensagem para X: texto" ou "mandar mensagem para X: texto"
    re.compile(
        r"(?:mandar|enviar)\s*(?:a seguinte)?\s*mensagem\s*(?:para|a)\s*[^:]+:\s*(.+)",
        re.I | re.S,
    ),
    # "lembrar de mandar mensagem para X: texto"
    re.compile(
        r"lembr(?:ar|e)\s+(?:me\s+)?(?:de\s+)?mandar\s+(?:a seguinte\s+)?mensagem\s+[^:]+:\s*(.+)",
        re.I | re.S,
    ),
    # "mensagem para [X]: texto" (mais genérico)
    re.compile(
        r"mensagem\s+para\s+[^:]+:\s*(.+)",
        re.I | re.S,
    ),
    # "send (the following) message to X: text"
    re.compile(
        r"send\s+(?:the following\s+)?message\s+to\s+[^:]+:\s*(.+)",
        re.I | re.S,
    ),
    # "recordar enviar mensaje a X: texto"
    re.compile(
        r"(?:recordar|recordarme)\s+(?:enviar\s+)?(?:la siguiente\s+)?mensaje\s+[^:]+:\s*(.+)",
        re.I | re.S,
    ),
]

# Fallback: último bloco após ": " quando o texto contém palavras-chave
_SEND_KEYWORDS = ("mensagem para", "mensaje para", "message to", "mandar mensagem", "enviar mensagem", "send message")

# Após extrair o texto, cortar meta-instruções do utilizador (ex.: ". Envie em uma mensagem isolada para que eu possa reencaminhar")
_META_INSTRUCTION_STARTS = (
    "envie em uma mensagem", "envie em mensagem", "envia em uma mensagem",
    "enviar em uma mensagem", "para que eu possa reencaminhar", "para eu poder reencaminhar",
    "so that i can forward", "so I can forward", "para poder encaminhar",
    "send in a separate message", "in a separate message", "isolada para",
)


def _trim_meta_instruction(msg: str) -> str:
    """Se a mensagem extraída termina com instrução do tipo 'Envie em mensagem isolada...', retorna só o texto a encaminhar."""
    if ". " not in msg:
        return msg.strip()
    parts = msg.split(". ", 1)
    first = parts[0].strip()
    rest = (parts[1] or "").strip().lower()
    for start in _META_INSTRUCTION_STARTS:
        if rest.startswith(start) or start in rest[:80]:
            return first
    return msg.strip()


def extract_message_to_forward(reminder_text: str) -> str | None:
    """
    Se o lembrete for do tipo "mandar mensagem para X: texto", retorna o texto a encaminhar.
    Caso contrário retorna None.
    """
    if not reminder_text or not reminder_text.strip():
        return None
    text = reminder_text.strip()
    for pat in _SEND_MESSAGE_PATTERNS:
        m = pat.search(text)
        if m:
            msg = _trim_meta_instruction(m.group(1).strip())
            if len(msg) >= 2 and len(msg) <= 2000:  # texto plausível
                return msg
    if any(kw in text.lower() for kw in _SEND_KEYWORDS) and ": " in text:
        idx = text.rfind(": ")
        if idx >= 0:
            msg = _trim_meta_instruction(text[idx + 2 :].strip())
            if len(msg) >= 2 and len(msg) <= 2000:
                return msg
    return None


def format_delivery_with_isolated_message(
    reminder_text: str,
    user_lang: str = "pt-BR",
) -> str | None:
    """
    Se o lembrete for "mandar mensagem para X: texto", retorna uma string formatada para entrega:
    uma linha introdutória + bloco isolado com o texto para o cliente copiar/encaminhar.
    Caso contrário retorna None (a entrega usa o fluxo normal).
    """
    msg = extract_message_to_forward(reminder_text)
    if not msg:
        return None
    labels = {
        "pt-PT": "📩 Mensagem para enviar/copiar:",
        "pt-BR": "📩 Mensagem para enviar/copiar:",
        "es": "📩 Mensaje para enviar/copiar:",
        "en": "📩 Message to send/copy:",
    }
    label = labels.get(user_lang, labels["en"])
    intros = {
        "pt-PT": "Lembrete: era para enviar esta mensagem. 😊",
        "pt-BR": "Lembrete: era para enviar esta mensagem. 😊",
        "es": "Recordatorio: era para enviar este mensaje. 😊",
        "en": "Reminder: you wanted to send this message. 😊",
    }
    intro = intros.get(user_lang, intros["en"])
    return f"{intro}\n\n{label}\n\n{msg}"
