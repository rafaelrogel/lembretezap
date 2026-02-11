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


def _seconds_to_lead_label(sec: int) -> str:
    """Converte segundos em etiqueta curta (ex.: 86400 -> '1 dia')."""
    if sec >= 86400:
        d = sec // 86400
        return f"{d} dia" if d == 1 else f"{d} dias"
    if sec >= 3600:
        h = sec // 3600
        return f"{h} hora" if h == 1 else f"{h} horas"
    m = sec // 60
    return f"{m} min" if m == 1 else f"{m} min"


def lead_time_confirmation(lang: LangCode, default_seconds: int | None, extra_seconds: list[int]) -> str:
    """Mensagem de confirmação após gravar preferências de avisos antes do evento."""
    default_str = _seconds_to_lead_label(default_seconds) if default_seconds else ""
    extra_str = ", ".join(_seconds_to_lead_label(s) for s in extra_seconds) if extra_seconds else ""
    if lang == "pt-PT":
        if extra_str:
            return f"Tudo certo! ✨ Aviso {default_str} antes + {extra_str}. Lembrete na hora. 😊"
        return f"Tudo certo! ✨ Aviso {default_str} antes e lembrete na hora. 😊"
    if lang == "pt-BR":
        if extra_str:
            return f"Beleza! ✨ Aviso {default_str} antes + {extra_str}. Lembrete na hora. 😊"
        return f"Beleza! ✨ Aviso {default_str} antes e lembrete na hora. 😊"
    if lang == "es":
        if extra_str:
            return f"¡Listo! ✨ Aviso {default_str} antes + {extra_str}. Recordatorio en el momento. 😊"
        return f"¡Listo! ✨ Aviso {default_str} antes y recordatorio en el momento. 😊"
    if extra_str:
        return f"Done! ✨ Reminder {default_str} before + {extra_str}. At event time. 😊"
    return f"Done! ✨ Reminder {default_str} before and at event time. 😊"


# Mensagem quando o onboarding termina (após cidade)
ONBOARDING_COMPLETE: dict[LangCode, str] = {
    "pt-PT": "Tudo certo! ✨ Já podes pedir lembretes, listas e eventos. Qualquer coisa, diz. 😊",
    "pt-BR": "Beleza! ✨ Já pode pedir lembretes, listas e eventos. Qualquer coisa, manda mensagem. 😊",
    "es": "¡Listo! ✨ Ya puedes pedir recordatorios, listas y eventos. Cualquier cosa, dilo. 😊",
    "en": "All set! ✨ You can ask for reminders, lists and events. Anything else, just say. 😊",
}

# Quando usamos timezone do número (cliente não deu cidade)
ONBOARDING_COMPLETE_TZ_FROM_PHONE: dict[LangCode, str] = {
    "pt-PT": "Sem cidade, usei o fuso do teu número. Podes mudar com /tz Cidade. /reset para refazer o registro. LGPD: só guardamos o essencial. 😊",
    "pt-BR": "Sem cidade, usei o fuso do seu número. Pode mudar com /tz Cidade. /reset para refazer o cadastro. LGPD: só guardamos o essencial. 😊",
    "es": "Sin ciudad, usé el huso de tu número. Puedes cambiar con /tz Ciudad. /reset para rehacer. RGPD: solo guardamos lo esencial. 😊",
    "en": "No city, using your number's timezone. Change with /tz City. /reset to redo. GDPR: we only store essentials. 😊",
}

# Nota de privacidade (LGPD/RGPD) a incluir no final do onboarding
ONBOARDING_PRIVACY_NOTE: dict[LangCode, str] = {
    "pt-PT": " Respeitamos LGPD/RGPD: só guardamos o essencial para o serviço funcionar.",
    "pt-BR": " Respeitamos LGPD/RGPD: só guardamos o essencial para o serviço funcionar.",
    "es": " Respetamos RGPD: solo guardamos lo esencial.",
    "en": " We respect GDPR: we only store essentials.",
}

# Mensagem quando completa onboarding sem cidade (timezone do número)
ONBOARDING_CITY_IMPORTANCE: dict[LangCode, str] = {
    "pt-PT": "A cidade ajuda a enviar lembretes na hora certa. Sem ela, uso o fuso do teu número.",
    "pt-BR": "A cidade ajuda a enviar lembretes na hora certa. Sem ela, uso o fuso do seu número.",
    "es": "La ciudad ayuda a enviar recordatorios a la hora correcta. Sin ella, uso el huso de tu número.",
    "en": "City helps send reminders at the right time. Without it, I use your number's timezone.",
}

# Sugestão de refazer cadastro (incluir no final do onboarding)
ONBOARDING_RESET_HINT: dict[LangCode, str] = {
    "pt-PT": " /reset para refazer o cadastro quando quiseres.",
    "pt-BR": " /reset para refazer o cadastro quando quiser.",
    "es": " /reset para rehacer el registro cuando quieras.",
    "en": " /reset to redo registration anytime.",
}


# Fallbacks para mensagem "fora do escopo" — curtos (~30% menores)
OUT_OF_SCOPE_FALLBACKS: dict[LangCode, list[str]] = {
    "pt-PT": [
        "Esse assunto foge ao que consigo fazer, mas adorava ajudar noutra coisa! 😊 Organizo lembretes e listas. Usa /help ou fala comigo.",
        "Não tenho superpoderes para isso. Posso ajudar com lembretes e listas. /help mostra os comandos.",
        "Nesse tema não consigo ajudar. O que faço: lembretes e listas. /help ou conversa comigo. ✨",
        "Isso fica fora da minha zona. Foco: organizar teu tempo. /help mostra tudo.",
        "Adorava ajudar noutra coisa. /help para comandos ou fala comigo. 😊",
    ],
    "pt-BR": [
        "Esse assunto foge do que consigo fazer, mas adoraria ajudar em outra coisa! 😊 Organizo lembretes e listas. Use /help ou fale comigo.",
        "Não tenho superpoderes para isso. Posso ajudar com lembretes e listas. /help mostra os comandos.",
        "Nesse tema não consigo ajudar. O que faço: lembretes e listas. /help ou converse comigo. ✨",
        "Isso fica fora da minha área. Foco: organizar seu tempo. /help mostra tudo.",
        "Adoraria ajudar em outra coisa. /help para comandos ou fale comigo. 😊",
    ],
    "es": [
        "Ese tema se sale de lo que puedo hacer, ¡pero me encantaría ayudarte! 😊 Organizo recordatorios y listas. Usa /help o habla conmigo.",
        "No tengo superpoderes para eso. Ayudo con recordatorios y listas. /help muestra comandos.",
        "En ese tema no puedo ayudar. Lo mío: recordatorios y listas. /help o conversa conmigo. ✨",
        "Eso se sale de mi zona. Foco: organizar tu tiempo. /help lo muestra todo.",
        "Me encantaría ayudarte en otra cosa. /help o háblame. 😊",
    ],
    "en": [
        "That's outside what I can do, but I'd love to help with something else! 😊 I do reminders and lists. Use /help or chat with me.",
        "I don't have superpowers for that. I help with reminders and lists. /help shows commands.",
        "I can't help with that topic. What I do: reminders and lists. /help or chat with me. ✨",
        "That's outside my lane. I focus on organising your time. /help shows everything.",
        "I'd love to help with something else. /help or chat with me. 😊",
    ],
}


# Durante o onboarding: "Quer comunicar noutro idioma? Temos pt-PT, pt-BR, es, en."
ONBOARDING_LANGUAGE_QUESTION: dict[LangCode, str] = {
    "pt-PT": "Queres comunicar noutro idioma? Temos português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Diz o código ou o nome do idioma, ou «não» para continuar. 😊",
    "pt-BR": "Quer comunicar em outro idioma? Temos português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Diga o código ou o nome do idioma, ou «não» para continuar. 😊",
    "es": "¿Quieres comunicarte en otro idioma? Tenemos portugués de Portugal (pt-PT), portugués de Brasil (pt-BR), español (es) e inglés (en). Di el código o el nombre del idioma, o «no» para seguir. 😊",
    "en": "Want to use another language? We have Portuguese from Portugal (pt-PT), Brazilian Portuguese (pt-BR), Spanish (es) and English (en). Say the code or language name, or «no» to continue. 😊",
}

# Quando o utilizador fala noutra língua (não suportada): só pt-PT, pt-BR, es, en
ONLY_SUPPORTED_LANGS_MESSAGE: dict[LangCode, str] = {
    "pt-PT": "Só consigo falar em português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Escolhe um deles ou usa /lang pt-pt, /lang pt-br, etc. 😊",
    "pt-BR": "Só consigo falar em português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Escolha um deles ou use /lang pt-pt, /lang pt-br, etc. 😊",
    "es": "Solo puedo hablar en portugués de Portugal (pt-PT), portugués de Brasil (pt-BR), español (es) e inglés (en). Elige uno o usa /lang pt-pt, /lang pt-br, etc. 😊",
    "en": "I can only speak Portuguese from Portugal (pt-PT), Brazilian Portuguese (pt-BR), Spanish (es) and English (en). Pick one or use /lang pt-pt, /lang pt-br, etc. 😊",
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
