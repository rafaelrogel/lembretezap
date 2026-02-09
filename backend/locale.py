"""Idioma por utilizador: inferência por prefixo telefónico e pedidos explícitos (pt-PT, pt-BR, es, en)."""

import re
import unicodedata
from typing import Literal

# Idiomas suportados
LangCode = Literal["pt-PT", "pt-BR", "es", "en"]
SUPPORTED_LANGS: list[LangCode] = ["pt-PT", "pt-BR", "es", "en"]

# Prefixos de país → idioma por defeito (apenas dígitos; sem +)
# Brasil
_DEFAULT_PT_BR = {"55"}
# Portugal
_DEFAULT_PT_PT = {"351"}
# Países hispânicos (Espanha + América Latina hispânica)
_DEFAULT_ES = {
    "34",   # Espanha
    "52",   # México
    "54",   # Argentina
    "57",   # Colômbia
    "58",   # Venezuela
    "51",   # Peru
    "56",   # Chile
    "593",  # Equador
    "595",  # Paraguai
    "598",  # Uruguai
    "591",  # Bolívia
    "503",  # El Salvador
    "502",  # Guatemala
    "505",  # Nicarágua
    "506",  # Costa Rica
    "507",  # Panamá
    "509",  # Haiti (também francês; es como fallback)
    "53",   # Cuba
    # 592 Guiana = inglês; 594 Guiana Francesa = francês → não incluídos; resto = en
}
# Resto → inglês por defeito


def _digits_from_chat_id(chat_id: str) -> str:
    """Extrai só os dígitos do chat_id (ex.: 5511999999999@s.whatsapp.net → 5511999999999)."""
    if not chat_id:
        return ""
    return "".join(c for c in str(chat_id).split("@")[0] if c.isdigit())


def phone_to_default_language(chat_id: str) -> LangCode:
    """
    Infere o idioma por defeito a partir do número (prefixo do país).
    BR → pt-BR, PT → pt-PT, hispânicos → es, resto → en.
    """
    digits = _digits_from_chat_id(chat_id)
    if not digits:
        return "en"
    # Tentar prefixos mais longos primeiro (ex.: 593 antes de 59)
    for prefix in sorted(_DEFAULT_PT_BR | _DEFAULT_PT_PT | _DEFAULT_ES, key=len, reverse=True):
        if digits.startswith(prefix):
            if prefix in _DEFAULT_PT_BR:
                return "pt-BR"
            if prefix in _DEFAULT_PT_PT:
                return "pt-PT"
            if prefix in _DEFAULT_ES:
                return "es"
    return "en"


# Padrões para pedido explícito de mudança de idioma (só os 4 suportados)
_LANG_SWITCH_PATTERNS: list[tuple[re.Pattern, LangCode]] = [
    # Português Portugal (português/portugues)
    (re.compile(r"\b(?:fala?r?\s+em\s+)?portugu[eê]s\s+(?:de\s+)?portugal\b", re.I), "pt-PT"),
    (re.compile(r"\b(?:speak\s+)?(?:in\s+)?portuguese\s+from\s+portugal\b", re.I), "pt-PT"),
    (re.compile(r"\bpt[- ]?pt\b", re.I), "pt-PT"),
    (re.compile(r"\bportugu[eê]s\s+europeu\b", re.I), "pt-PT"),
    # Português Brasil
    (re.compile(r"\b(?:fala?r?\s+em\s+)?portugu[eê]s\s+(?:do\s+)?brasil\b", re.I), "pt-BR"),
    (re.compile(r"\b(?:fala?r?\s+em\s+)?portugu[eê]s\s+(?:do\s+)?br\b", re.I), "pt-BR"),
    (re.compile(r"\b(?:speak\s+)?(?:in\s+)?brazilian\s+portuguese\b", re.I), "pt-BR"),
    (re.compile(r"\bpt[- ]?br\b", re.I), "pt-BR"),
    # Espanhol (spanish / español / espanol / espanhol)
    (re.compile(r"\b(?:speak\s+)?(?:in\s+)?spanish\b", re.I), "es"),
    (re.compile(r"\b(?:habla?r?\s+en\s+)?(?:español|espanol)\b", re.I), "es"),
    (re.compile(r"\b(?:fala?r?\s+em\s+)?espanhol\b", re.I), "es"),
    (re.compile(r"\b(?:em\s+)?espanhol\b", re.I), "es"),
    # Inglês (inglês/inglés/ingles sem acento)
    (re.compile(r"\b(?:fala?r?\s+em\s+)?ingl[eêé]s\b", re.I), "en"),
    (re.compile(r"\b(?:habla?r?\s+en\s+)?ingl[eé]s\b", re.I), "en"),
    (re.compile(r"\b(?:speak\s+)?(?:in\s+)?english\b", re.I), "en"),
    (re.compile(r"\b(?:em\s+)?ingl[eêé]s\b", re.I), "en"),
]


def language_switch_confirmation_message(lang: LangCode) -> str:
    """Mensagem curta de confirmação quando o utilizador pede mudança de idioma."""
    msgs = {
        "pt-PT": "Combinado, daqui em diante falo em português de Portugal. 📋",
        "pt-BR": "Beleza! A partir de agora falo em português do Brasil. 📋",
        "es": "¡De acuerdo! A partir de ahora hablo en español. 📋",
        "en": "Sure! From now on I'll speak in English. 📋",
    }
    return msgs.get(lang, msgs["en"])


# Pergunta "como gostaria de ser chamado" (fallback quando não há Xiaomi)
PREFERRED_NAME_QUESTION: dict[LangCode, str] = {
    "pt-PT": "Como gostaria que eu te chamasse?",
    "pt-BR": "Como você gostaria que eu te chamasse?",
    "es": "¿Cómo te gustaría que te llamara?",
    "en": "What would you like me to call you?",
}


def preferred_name_confirmation(lang: LangCode, name: str) -> str:
    """Mensagem de confirmação após gravar o nome preferido do utilizador."""
    msgs = {
        "pt-PT": f"Obrigado! A partir de agora vou chamar-te {name}. 📋",
        "pt-BR": f"Valeu! A partir de agora vou te chamar de {name}. 📋",
        "es": f"¡Gracias! A partir de ahora te llamaré {name}. 📋",
        "en": f"Thanks! I'll call you {name} from now on. 📋",
    }
    return msgs.get(lang, msgs["en"])


# Fallbacks para mensagem "fora do escopo" por idioma (quando não há Xiaomi ou falha)
OUT_OF_SCOPE_FALLBACKS: dict[LangCode, list[str]] = {
    "pt-PT": [
        "Sou só o teu organizador: lembretes, listas e eventos. Experimenta /lembrete, /list ou /filme. 📋",
        "Por aqui só organizo a vida: lembretes, listas, filmes. Manda /lembrete, /list ou /filme! ✨",
        "Nesse assunto não te consigo ajudar — sou só para lembretes, listas e eventos. /lembrete, /list, /filme. 😊",
    ],
    "pt-BR": [
        "Sou só seu organizador: lembretes, listas e eventos. Use /lembrete, /list ou /filme. 📋",
        "Por aqui só organizo sua vida: lembretes, listas, filmes. Manda /lembrete, /list ou /filme! ✨",
        "Nesse assunto não consigo ajudar — sou só para lembretes, listas e eventos. /lembrete, /list, /filme. 😊",
    ],
    "es": [
        "Solo soy tu organizador: recordatorios, listas y eventos. Prueba /lembrete, /list o /filme. 📋",
        "Por aquí solo organizo: recordatorios, listas, películas. Envía /lembrete, /list o /filme. ✨",
        "En ese tema no puedo ayudarte — solo recordatorios, listas y eventos. /lembrete, /list, /filme. 😊",
    ],
    "en": [
        "I'm just your organizer: reminders, lists and events. Try /lembrete, /list or /filme. 📋",
        "Here I only handle reminders, lists and events. Send /lembrete, /list or /filme! ✨",
        "I can't help with that — only reminders, lists and events. /lembrete, /list, /filme. 😊",
    ],
}


def parse_language_switch_request(message: str) -> LangCode | None:
    """
    Detecta se a mensagem é um pedido explícito para falar noutro idioma (pt-PT, pt-BR, es, en).
    Retorna o código do idioma pedido ou None.
    """
    if not message or not message.strip():
        return None
    text = message.strip()
    try:
        text = unicodedata.normalize("NFC", text)
    except Exception:
        pass
    for pattern, lang in _LANG_SWITCH_PATTERNS:
        if pattern.search(text):
            return lang
    return None
