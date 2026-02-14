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


# Quando o utilizador pede idioma que já está ativo (ex.: "falar em português do brasil" e já está pt-BR)
LANGUAGE_ALREADY_MSG: dict[LangCode, str] = {
    "pt-PT": "Já estamos em português de Portugal! 😊",
    "pt-BR": "Já estamos em português do Brasil! 😊",
    "es": "¡Ya estamos en español! 😊",
    "en": "We're already in English! 😊",
}


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

# Dica sobre emojis em lembretes (feito / soneca / não feito)
ONBOARDING_EMOJI_TIP: dict[LangCode, str] = {
    "pt-PT": "\n\n💡 Nos lembretes: 👍 (feito, confirma com sim); ⏰ (adiar 5 min, máx 3x); 👎 (reagendar).",
    "pt-BR": "\n\n💡 Nos lembretes: 👍 (feito, confirme com sim); ⏰ (adiar 5 min, máx 3x); 👎 (reagendar).",
    "es": "\n\n💡 En recordatorios: 👍 (hecho, confirma con sí); ⏰ (pospóner 5 min, máx 3x); 👎 (reprogramar).",
    "en": "\n\n💡 On reminders: 👍 (done, confirm with yes); ⏰ (snooze 5 min, max 3x); 👎 (reschedule).",
}


# Fallbacks para mensagem "fora do escopo" — curtos (~30% menores)
OUT_OF_SCOPE_FALLBACKS: dict[LangCode, list[str]] = {
    "pt-PT": [
        "Esse assunto foge ao que consigo fazer, mas adorava ajudar noutra coisa! 😊 Organizo lembretes e listas. Usa /help ou fala comigo por mensagem ou áudio.",
        "Não tenho superpoderes para isso. Posso ajudar com lembretes e listas. /help mostra os comandos. Ou escreve/envia áudio.",
        "Nesse tema não consigo ajudar. O que faço: lembretes e listas. /help ou conversa por mensagem/áudio. ✨",
        "Isso fica fora da minha zona. Foco: organizar teu tempo. /help mostra tudo. Podes escrever ou mandar áudio.",
        "Adorava ajudar noutra coisa. /help para comandos ou fala por mensagem/áudio. 😊",
    ],
    "pt-BR": [
        "Esse assunto foge do que consigo fazer, mas adoraria ajudar em outra coisa! 😊 Organizo lembretes e listas. Use /help ou fale comigo por mensagem ou áudio.",
        "Não tenho superpoderes para isso. Posso ajudar com lembretes e listas. /help mostra os comandos. Ou escreva/envie áudio.",
        "Nesse tema não consigo ajudar. O que faço: lembretes e listas. /help ou converse por mensagem/áudio. ✨",
        "Isso fica fora da minha área. Foco: organizar seu tempo. /help mostra tudo. Pode escrever ou mandar áudio.",
        "Adoraria ajudar em outra coisa. /help para comandos ou fale por mensagem/áudio. 😊",
    ],
    "es": [
        "Ese tema se sale de lo que puedo hacer, ¡pero me encantaría ayudarte! 😊 Organizo recordatorios y listas. Usa /help o háblame por mensaje o audio.",
        "No tengo superpoderes para eso. Ayudo con recordatorios y listas. /help muestra comandos. O escribe/envía audio.",
        "En ese tema no puedo ayudar. Lo mío: recordatorios y listas. /help o conversa por mensaje/audio. ✨",
        "Eso se sale de mi zona. Foco: organizar tu tiempo. /help lo muestra todo. Puedes escribir o mandar audio.",
        "Me encantaría ayudarte en otra cosa. /help o háblame por mensaje/audio. 😊",
    ],
    "en": [
        "That's outside what I can do, but I'd love to help with something else! 😊 I do reminders and lists. Use /help or message me / send audio.",
        "I don't have superpowers for that. I help with reminders and lists. /help shows commands. Or type/send audio.",
        "I can't help with that topic. What I do: reminders and lists. /help or chat by message/audio. ✨",
        "That's outside my lane. I focus on organising your time. /help shows everything. You can type or send audio.",
        "I'd love to help with something else. /help or message me / send audio. 😊",
    ],
}


# Fallback quando o agente não produz resposta (ex.: mensagem muito longa, stress test)
AGENT_NO_RESPONSE_FALLBACK: dict[LangCode, str] = {
    "pt-PT": "Desculpa, não consegui processar completamente. Podes reformular ou dividir em partes mais pequenas? /help mostra os comandos. Podes escrever ou enviar áudio. 😊",
    "pt-BR": "Desculpa, não consegui processar completamente. Pode reformular ou dividir em partes menores? /help mostra os comandos. Pode escrever ou enviar áudio. 😊",
    "es": "Lo siento, no pude procesar completamente. ¿Puedes reformular o dividir en partes más pequeñas? /help muestra los comandos. Puedes escribir o enviar audio. 😊",
    "en": "Sorry, I couldn't process that fully. Can you rephrase or break it into smaller parts? /help shows the commands. You can type or send audio. 😊",
}


# Durante o onboarding: "Quer comunicar noutro idioma? Temos pt-PT, pt-BR, es, en."
ONBOARDING_LANGUAGE_QUESTION: dict[LangCode, str] = {
    "pt-PT": "Queres comunicar noutro idioma? Temos português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Diz o código ou o nome do idioma, ou «não» para continuar. 😊",
    "pt-BR": "Quer comunicar em outro idioma? Temos português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Diga o código ou o nome do idioma, ou «não» para continuar. 😊",
    "es": "¿Quieres comunicarte en otro idioma? Tenemos portugués de Portugal (pt-PT), portugués de Brasil (pt-BR), español (es) e inglés (en). Di el código o el nombre del idioma, o «no» para seguir. 😊",
    "en": "Want to use another language? We have Portuguese from Portugal (pt-PT), Brazilian Portuguese (pt-BR), Spanish (es) and English (en). Say the code or language name, or «no» to continue. 😊",
}

# Intervalo mínimo para lembretes recorrentes
REMINDER_MIN_INTERVAL_30MIN: dict[LangCode, str] = {
    "pt-PT": "O intervalo mínimo para lembretes recorrentes é 30 minutos. Ex.: «a cada 30 min» ou «a cada 1 hora».",
    "pt-BR": "O intervalo mínimo para lembretes recorrentes é 30 minutos. Ex.: «a cada 30 min» ou «a cada 1 hora».",
    "es": "El intervalo mínimo para recordatorios recurrentes es 30 minutos. Ej.: «cada 30 min» o «cada 1 hora».",
    "en": "The minimum interval for recurring reminders is 30 minutes. E.g. «every 30 min» or «every 1 hour».",
}
REMINDER_MIN_INTERVAL_2H: dict[LangCode, str] = {
    "pt-PT": "O intervalo mínimo para lembretes recorrentes é 2 horas. Ex.: «a cada 2 horas» ou «a cada 3 horas».",
    "pt-BR": "O intervalo mínimo para lembretes recorrentes é 2 horas. Ex.: «a cada 2 horas» ou «a cada 3 horas».",
    "es": "El intervalo mínimo para recordatorios recurrentes es 2 horas. Ej.: «cada 2 horas» o «cada 3 horas».",
    "en": "The minimum interval for recurring reminders is 2 hours. E.g. «every 2 hours» or «every 3 hours».",
}
REMINDER_LIMIT_EXCEEDED: dict[LangCode, str] = {
    "pt-PT": "Tens o limite máximo de 50 lembretes ativos. Remove alguns com 👎 ou /lembrete antes de adicionar mais.",
    "pt-BR": "Você atingiu o limite máximo de 50 lembretes ativos. Remova alguns com 👎 ou /lembrete antes de adicionar mais.",
    "es": "Has alcanzado el límite máximo de 50 recordatorios activos. Elimina algunos con 👎 o /lembrete antes de añadir más.",
    "en": "You've reached the maximum limit of 50 active reminders. Remove some with 👎 or /lembrete before adding more.",
}

# Mensagens de áudio (voice messages)
AUDIO_TOO_LONG: dict[LangCode, str] = {
    "pt-PT": "O áudio é um pouco longo. Consegues enviar uma mensagem mais curta?",
    "pt-BR": "O áudio está um pouco longo. Consegue enviar uma mensagem mais curta?",
    "es": "El audio es un poco largo. ¿Puedes enviar un mensaje más corto?",
    "en": "The audio is a bit long. Can you send a shorter message?",
}
AUDIO_TOO_LARGE: dict[LangCode, str] = {
    "pt-PT": "O áudio é um pouco longo. Consegues enviar uma mensagem mais curta?",
    "pt-BR": "O áudio está um pouco longo. Consegue enviar uma mensagem mais curta?",
    "es": "El audio es un poco largo. ¿Puedes enviar un mensaje más corto?",
    "en": "The audio is a bit long. Can you send a shorter message?",
}
AUDIO_FORWARDED: dict[LangCode, str] = {
    "pt-PT": "Só aceito áudios gravados por ti. Não reencaminhes mensagens de voz.",
    "pt-BR": "Só aceito áudios gravados por você. Não encaminhe mensagens de voz.",
    "es": "Solo acepto audios grabados por ti. No reenvíes mensajes de voz.",
    "en": "I only accept audio you've recorded yourself. Don't forward voice messages.",
}
AUDIO_NOT_ALLOWED: dict[LangCode, str] = {
    "pt-PT": "Transcrição de áudio não está disponível para o teu número. Contacta o administrador se quiseres ativar.",
    "pt-BR": "Transcrição de áudio não está disponível para o seu número. Contate o administrador se quiser ativar.",
    "es": "La transcripción de audio no está disponible para tu número. Contacta al administrador si quieres activarla.",
    "en": "Audio transcription isn't available for your number. Contact the admin if you'd like it enabled.",
}
AUDIO_TRANSCRIBE_FAILED: dict[LangCode, str] = {
    "pt-PT": "Não consegui transcrever o áudio. Tenta novamente ou escreve a mensagem.",
    "pt-BR": "Não consegui transcrever o áudio. Tente novamente ou escreva a mensagem.",
    "es": "No pude transcribir el audio. Intenta de nuevo o escribe el mensaje.",
    "en": "I couldn't transcribe the audio. Try again or type your message.",
}
AUDIO_NOT_RECEIVED: dict[LangCode, str] = {
    "pt-PT": "Áudio não recebido. Envia novamente.",
    "pt-BR": "Áudio não recebido. Envie novamente.",
    "es": "Audio no recibido. Envíalo de nuevo.",
    "en": "Audio not received. Please send again.",
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
