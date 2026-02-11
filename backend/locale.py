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
            return f"Tudo certo! ✨ Receberás um aviso {default_str} antes, mais avisos a {extra_str} antes, e o lembrete na hora do evento. Qualquer coisa, é só dizeres. 😊"
        return f"Tudo certo! ✨ Receberás um aviso {default_str} antes e o lembrete na hora do evento. 😊"
    if lang == "pt-BR":
        if extra_str:
            return f"Beleza! ✨ Você receberá um aviso {default_str} antes, mais avisos a {extra_str} antes, e o lembrete na hora do evento. Qualquer coisa, manda mensagem. 😊"
        return f"Beleza! ✨ Você receberá um aviso {default_str} antes e o lembrete na hora do evento. 😊"
    if lang == "es":
        if extra_str:
            return f"¡Listo! ✨ Recibirás un aviso {default_str} antes, más avisos a {extra_str} antes, y el recordatorio en el momento del evento. Cualquier cosa, dila. 😊"
        return f"¡Listo! ✨ Recibirás un aviso {default_str} antes y el recordatorio en el momento del evento. 😊"
    if extra_str:
        return f"Done! ✨ You'll get a reminder {default_str} before, plus reminders at {extra_str} before, and at the event time. 😊"
    return f"Done! ✨ You'll get a reminder {default_str} before and at the event time. 😊"


# Mensagem quando o onboarding termina (após cidade; sem perguntar avisos antes do evento)
ONBOARDING_COMPLETE: dict[LangCode, str] = {
    "pt-PT": "Tudo certo! ✨ Já podes pedir lembretes, listas e eventos. Para reuniões e compromissos, aviso-te antes na hora que fizer sentido. Qualquer coisa, é só dizeres. 😊",
    "pt-BR": "Beleza! ✨ Já pode pedir lembretes, listas e eventos. Para reuniões e compromissos, te aviso antes na hora que fizer sentido. Qualquer coisa, manda mensagem. 😊",
    "es": "¡Listo! ✨ Ya puedes pedir recordatorios, listas y eventos. Para reuniones y compromisos, te aviso antes cuando tenga sentido. Cualquier cosa, dilo. 😊",
    "en": "All set! ✨ You can ask for reminders, lists and events. For meetings and appointments I'll remind you in advance when it makes sense. Anything else, just say. 😊",
}


# Fallbacks para mensagem "fora do escopo": referem /help para comandos e "conversar comigo" (assistente IA).
OUT_OF_SCOPE_FALLBACKS: dict[LangCode, list[str]] = {
    "pt-PT": [
        "Esse assunto foge ao que consigo fazer — mas adorava ajudar noutra coisa! 😊 Por aqui organizo lembretes, listas e até filmes ou livros que queiras ver. Podes usar /help para ver todos os comandos, ou simplesmente conversar comigo: sou o teu assistente pessoal de IA.",
        "Não tenho superpoderes para isso, mas posso ser o teu assistente do dia a dia! 📋 Lembretes, listas, compromissos. Manda /help para ver o que está disponível, ou fala comigo em linguagem natural que eu ajudo a organizar.",
        "Nesse tema não te consigo ajudar, desculpa! O que faço bem é lembretes, listas e um bocadinho de cultura. Usa /help para ver os comandos, ou conversa comigo — sou aqui o teu assistente pessoal. ✨",
        "Ah, isso fica fora da minha zona! 😅 Por aqui o foco é organizar o teu tempo. Queres ver o que podes fazer? /help mostra tudo. Ou diz-me em palavras tuas o que precisas e eu guio-te.",
        "Não chego a esse ponto, mas adorava ajudar noutra coisa. Podes escrever /help para ver os comandos, ou falar comigo à vontade — sou o teu assistente de lembretes e listas. 😊",
    ],
    "pt-BR": [
        "Esse assunto foge do que eu consigo fazer — mas adoraria ajudar em outra coisa! 😊 Por aqui eu organizo lembretes, listas e até filmes e livros que você queira ver. Você pode usar /help para ver todos os comandos, ou simplesmente conversar comigo: sou seu assistente pessoal de IA.",
        "Não tenho superpoderes para isso, mas posso ser seu assistente do dia a dia! 📋 Lembretes, listas, compromissos. Mande /help para ver o que está disponível, ou fale comigo em linguagem natural que eu ajudo a organizar.",
        "Nesse tema não consigo te ajudar, desculpa! O que eu faço bem é lembretes, listas e um pouquinho de cultura. Use /help para ver os comandos, ou converse comigo — sou seu assistente pessoal aqui. ✨",
        "Ah, isso fica fora da minha área! 😅 Por aqui o foco é organizar seu tempo. Quer ver o que você pode fazer? /help mostra tudo. Ou me diga com suas palavras o que precisa que eu te guio.",
        "Não chego a esse ponto, mas adoraria ajudar em outra coisa. Você pode digitar /help para ver os comandos, ou falar comigo à vontade — sou seu assistente de lembretes e listas. 😊",
    ],
    "es": [
        "Ese tema se sale de lo que puedo hacer — ¡pero me encantaría ayudarte en otra cosa! 😊 Por aquí organizo recordatorios, listas y hasta películas o libros. Puedes usar /help para ver todos los comandos, o simplemente conversar conmigo: soy tu asistente personal de IA.",
        "No tengo superpoderes para eso, pero puedo ser tu asistente del día a día. 📋 Recordatorios, listas, compromisos. Envía /help para ver qué hay disponible, o háblame con naturalidad y te ayudo a organizarte.",
        "En ese tema no te puedo ayudar, ¡perdón! Lo mío son recordatorios, listas y un poco de cultura. Usa /help para ver los comandos, o conversa conmigo — soy tu asistente personal aquí. ✨",
        "¡Eso se sale de mi zona! 😅 Por aquí me centro en organizar tu tiempo. ¿Quieres ver qué puedes hacer? /help lo muestra todo. O dime con tus palabras qué necesitas y te guío.",
        "No llego a ese punto, pero me encantaría ayudarte en otra cosa. Puedes escribir /help para ver los comandos, o hablar conmigo con libertad — soy tu asistente de recordatorios y listas. 😊",
    ],
    "en": [
        "That's a bit outside what I can do — but I'd love to help with something else! 😊 Here I help with reminders, lists, and even films or books you want to watch. You can use /help to see all commands, or just chat with me: I'm your personal AI assistant.",
        "I don't have superpowers for that, but I can be your day-to-day assistant! 📋 Reminders, lists, appointments. Send /help to see what's available, or talk to me in plain language and I'll help you get organised.",
        "I can't help with that topic, sorry! What I do well is reminders, lists, and a bit of culture. Use /help to see the commands, or chat with me — I'm your personal assistant here. ✨",
        "That's outside my lane! 😅 Here I focus on organising your time. Want to see what you can do? /help shows everything. Or tell me in your own words what you need and I'll guide you.",
        "I can't go that far, but I'd love to help with something else. You can type /help to see the commands, or chat with me freely — I'm your reminders and lists assistant. 😊",
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
