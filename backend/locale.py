"""Idioma por usuário: inferência por prefixo telefônico e pedidos explícitos (pt-PT, pt-BR, es, en)."""

import re
import unicodedata
from typing import Literal

# Idiomas suportados
LangCode = Literal["pt-PT", "pt-BR", "es", "en"]
SUPPORTED_LANGS: list[LangCode] = ["pt-PT", "pt-BR", "es", "en"]

# Prefixos de país → idioma padrão (apenas dígitos; sem +)
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
# Resto → inglês padrão


def _digits_from_chat_id(chat_id: str) -> str:
    """Extrai só os dígitos do chat_id (ex.: 5511999999999@s.whatsapp.net → 5511999999999).
    Ignora IDs @lid pois não são números de telefone reais.
    """
    if not chat_id or "@lid" in chat_id:
        return ""
    return "".join(c for c in str(chat_id).split("@")[0] if c.isdigit())


def phone_to_default_language(chat_id: str) -> LangCode:
    """
    Infere o idioma padrão a partir do número (prefixo do país).
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


def resolve_response_language(
    db_lang: LangCode,
    chat_id: str,
    phone_for_locale: str | None = None,
) -> LangCode:
    """
    Retorna o idioma a usar nas respostas.
    Regra: o idioma guardado na DB (escolha explícita do usuário) tem sempre prioridade.
    Número e timezone não sobrescrevem a escolha; só entram quando não há idioma guardado
    (get_user_language usa phone_for_locale para inferir nesse caso).
    """
    return db_lang


# Padrões para pedido explícito de mudança de idioma (só os 4 suportados)
# Ordem importa: mais específicos primeiro (Portugal/Brasil antes do genérico "português")
_LANG_SWITCH_PATTERNS: list[tuple[re.Pattern, LangCode]] = [
    # Português Portugal (português/portugues)
    (re.compile(r"\b(?:fala?r?\s+em\s+)?portugu[eê]s\s+(?:de\s+)?portugal\b", re.I), "pt-PT"),
    (re.compile(r"\b(?:speak\s+)?(?:in\s+)?portuguese\s+from\s+portugal\b", re.I), "pt-PT"),
    (re.compile(r"\bpt[- ]?pt\b", re.I), "pt-PT"),
    (re.compile(r"\bportugu[eê]s\s+europeu\b", re.I), "pt-PT"),
    (re.compile(r"\bptpt\b", re.I), "pt-PT"),
    # Português Brasil
    (re.compile(r"\b(?:fala?r?\s+em\s+)?portugu[eê]s\s+(?:do\s+)?brasil\b", re.I), "pt-BR"),
    (re.compile(r"\b(?:fala?r?\s+em\s+)?portugu[eê]s\s+(?:do\s+)?br\b", re.I), "pt-BR"),
    (re.compile(r"\b(?:speak\s+)?(?:in\s+)?brazilian\s+portuguese\b", re.I), "pt-BR"),
    (re.compile(r"\bpt[- ]?br\b", re.I), "pt-BR"),
    (re.compile(r"\bptbr\b", re.I), "pt-BR"),
    # Pedido de NÃO falar em espanhol → inferir pt-BR/pt-PT pelo número
    (re.compile(r"\b(?:n[aã]o\s+)?fala?e?\s+em\s+espanhol\b", re.I), "pt"),
    (re.compile(r"\bpara\s+de\s+fala?r?\s+em\s+espanhol\b", re.I), "pt"),
    # Português genérico (fale/fala em português) — inferir pt-PT/pt-BR pelo número (ver parse_language_switch_request)
    # \w+ cobre ê, é, e e variantes de codificação (ex.: ê como 2 chars)
    (re.compile(r"\b(?:fala?e?\s+(?:comigo\s+)?(?:em\s+)?|em\s+)portugu\w+s\b", re.I), "pt"),  # "pt" = inferir do número
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
    """Mensagem curta de confirmação quando o usuário pede mudança de idioma."""
    msgs = {
        "pt-PT": "Combinado, daqui em diante falo em português de Portugal. 📋",
        "pt-BR": "Beleza! A partir de agora falo em português do Brasil. 📋",
        "es": "¡De acuerdo! A partir de ahora hablo en español. 📋",
        "en": "Sure! From now on I'll speak in English. 📋",
    }
    return msgs.get(lang, msgs["en"])


# Quando o usuário pede idioma que já está ativo (ex.: "falar em português do brasil" e já está pt-BR)
LANGUAGE_ALREADY_MSG: dict[LangCode, str] = {
    "pt-PT": "Já estamos em português de Portugal! 😊",
    "pt-BR": "Já estamos em português do Brasil! 😊",
    "es": "¡Ya estamos en español! 😊",
    "en": "We're already in English! 😊",
}


# Pergunta "como gostaria de ser chamado" (fallback quando não há Xiaomi)
PREFERRED_NAME_QUESTION: dict[LangCode, str] = {
    "pt-PT": "Como gostarias que eu te chamasse?",
    "pt-BR": "Como você gostaria que eu te chamasse?",
    "es": "¿Cómo te gustaría que te llamara?",
    "en": "What would you like me to call you?",
}


AMBIGUOUS_CHOICE_MSG: dict[LangCode, str] = {
    "pt-PT": "Queres que eu crie uma *lista de afazeres* (to-do) com estes itens ou preferes registar cada um como *lembrete* com horário? Também posso fazer *os dois*. Responde: *lista*, *lembretes* ou *os dois*.",
    "pt-BR": "Você quer que eu crie uma *lista de tarefas* (to-do) com estes itens ou prefere registrar cada um como *lembrete* com horário? Também posso fazer *os dois*. Responda: *lista*, *lembretes* ou *os dois*.",
    "es": "¿Quieres que cree una *lista de tareas* (to-do) con estos elementos o prefieres registrar cada uno como *recordatorio* con horario? También puedo hacer *ambos*. Responde: *lista*, *recordatorios* o *ambos*.",
    "en": "Do you want me to create a *to-do list* with these items or would you rather register each one as a *reminder* with a time? I can also do *both*. Reply: *list*, *reminders*, or *both*.",
}


POMODORO_ALREADY_ACTIVE: dict[LangCode, str] = {
    "pt-PT": "Já tens um Pomodoro ativo. /pomodoro stop para cancelar e iniciar outro.",
    "pt-BR": "Você já tem um Pomodoro ativo. /pomodoro stop para cancelar e iniciar outro.",
    "es": "Ya tienes un Pomodoro activo. /pomodoro stop para cancelar e iniciar otro.",
    "en": "You already have a Pomodoro active. /pomodoro stop to cancel and start another.",
}


def preferred_name_confirmation(lang: LangCode, name: str) -> str:
    """Mensagem de confirmação após gravar o nome preferido do usuário."""
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

# --- Onboarding simplificado: fuso primeiro (sem bloquear o sistema) ---
# Intro: o mais importante é onde a pessoa está para lembretes na hora certa
ONBOARDING_INTRO_TZ_FIRST: dict[LangCode, str] = {
    "pt-PT": "Olá! Sou a tua assistente de organização — listas, lembretes e agenda. 📋",
    "pt-BR": "Oi! Sou sua assistente de organização — listas, lembretes e agenda. 📋",
    "es": "¡Hola! Soy tu asistente de organización — listas, recordatorios y agenda. 📋",
    "en": "Hi! I'm your organization assistant — lists, reminders and agenda. 📋",
}
# Pergunta única: cidade OU que horas são aí (informação mais importante = fuso)
ONBOARDING_ASK_CITY_OR_TIME: dict[LangCode, str] = {
    "pt-PT": "Para enviar os lembretes na hora certa, preciso saber onde estás. Em que cidade vives? (Ou diz-me que horas são aí agora.)",
    "pt-BR": "Para enviar os lembretes na hora certa, preciso saber onde você está. Em que cidade você mora? (Ou me diga que horas são aí agora.)",
    "es": "Para enviar los recordatorios a la hora correcta, necesito saber dónde estás. ¿En qué ciudad vives? (O dime qué hora es ahí ahora.)",
    "en": "To send reminders at the right time, I need to know where you are. Which city do you live in? (Or tell me what time it is there now.)",
}
# Retry: perguntar só a hora
ONBOARDING_ASK_TIME_FALLBACK: dict[LangCode, str] = {
    "pt-PT": "Que horas são aí agora? (Assim acerto o fuso dos teus lembretes.)",
    "pt-BR": "Que horas são aí agora? (Assim acerto o fuso dos seus lembretes.)",
    "es": "¿Qué hora es ahí ahora? (Así ajusto el huso de tus recordatorios.)",
    "en": "What time is it there now? (So I can set your reminder times right.)",
}
# Confirmação: "Ah, [data], [hora]. Confere?"
def onboarding_time_confirm_message(lang: LangCode, date_str: str, time_str: str) -> str:
    """Mensagem de confirmação: data e hora interpretados. Ex.: 'Ah, 8 de fev, 14:30. Confere?'"""
    templates = {
        "pt-PT": f"Ah, {date_str}, {time_str}. Confere?",
        "pt-BR": f"Ah, {date_str}, {time_str}. Confere?",
        "es": f"Ah, {date_str}, {time_str}. ¿Confirma?",
        "en": f"So, {date_str}, {time_str}. Correct?",
    }
    return templates.get(lang, templates["en"])
# Fuso definido a partir da hora (não da cidade)
ONBOARDING_TZ_SET_FROM_TIME: dict[LangCode, str] = {
    "pt-PT": "Fuso definido. Podes mudar quando quiseres com /tz ou /fuso.",
    "pt-BR": "Fuso definido. Você pode mudar quando quiser com /tz ou /fuso.",
    "es": "Huso definido. Puedes cambiar cuando quieras con /tz o /fuso.",
    "en": "Timezone set. You can change anytime with /tz or /fuso.",
}
# Nudge quando falta fuso (não bloquear; lembrete suave)
NUDGE_TZ_WHEN_MISSING: dict[LangCode, str] = {
    "pt-PT": "Quando puderes, diz a tua cidade ou que horas são aí para os lembretes chegarem na hora. 😊",
    "pt-BR": "Quando puder, diga sua cidade ou que horas são aí para os lembretes chegarem na hora. 😊",
    "es": "Cuando puedas, dime tu ciudad o qué hora es ahí para que los recordatorios lleguen a tiempo. 😊",
    "en": "When you can, tell me your city or what time it is there so reminders arrive on time. 😊",
}

# Apelo ao uso diário: fala comigo todos os dias para eu aprender e não ficar sozinho (call to action + reduz risco spam)
ONBOARDING_DAILY_USE_APPEAL: dict[LangCode, str] = {
    "pt-PT": "\n\n🫶 Fala comigo todos os dias — assim aprendo contigo e não fico sozinho. Qualquer dúvida ou lembrete, manda mensagem ou áudio.",
    "pt-BR": "\n\n🫶 Fale comigo todos os dias — assim eu aprendo com você e não fico sozinho. Qualquer dúvida ou lembrete, mande mensagem ou áudio.",
    "es": "\n\n🫶 Háblame todos los días — así aprendo contigo y no me quedo solo. Cualquier duda o recordatorio, manda mensaje o audio.",
    "en": "\n\n🫶 Talk to me every day — that way I learn from you and don't feel alone. Any question or reminder, just message or send audio.",
}

# Dica sobre emojis em lembretes (feito / soneca / não feito)
ONBOARDING_EMOJI_TIP: dict[LangCode, str] = {
    "pt-PT": "\n\n💡 Quando receberes um lembrete, reage à mensagem:\n• 👍 (feito) — depois confirma com *sim*\n• ⏰ (adiar 5 min, máx 3x)\n• 👎 (remover) — pergunto se queres alterar horário ou cancelar\n\nOu escreve/envia áudio, ex.: feito, remover, adiar 1 hora.",
    "pt-BR": "\n\n💡 Quando receber um lembrete, reaja à mensagem:\n• 👍 (feito) — depois confirme com *sim*\n• ⏰ (adiar 5 min, máx 3x)\n• 👎 (remover) — pergunto se você quer alterar horário ou cancelar\n\nOu escreva/envie áudio, ex.: feito, remover, adiar 1 hora.",
    "es": "\n\n💡 Cuando recibas un recordatorio, reacciona al mensaje:\n• 👍 (hecho) — luego confirma con *sí*\n• ⏰ (pospóner 5 min, máx 3x)\n• 👎 (eliminar) — pregunto si quieres cambiar horario o cancelar\n\nO escribe/envía audio, ej.: hecho, eliminar, posponer 1 hora.",
    "en": "\n\n💡 When you receive a reminder, react to the message:\n• 👍 (done) — then confirm with *yes*\n• ⏰ (snooze 5 min, max 3x)\n• 👎 (remove) — I'll ask if you want to change time or cancel\n\nOr type/send audio, e.g. done, remove, snooze 1 hour.",
}


# Fallbacks para mensagem "fora do escopo" — indicar claramente que /help é comando a digitar
OUT_OF_SCOPE_FALLBACKS: dict[LangCode, list[str]] = {
    "pt-PT": [
        "Esse assunto foge ao que consigo fazer, mas adorava ajudar noutra coisa! 😊 Organizo lembretes e listas. Podes digitar /help para ver a lista de comandos, ou falar por mensagem/áudio.",
        "Não tenho superpoderes para isso. Posso ajudar com lembretes e listas. Digita /help para ver os comandos; ou escreve/envia áudio.",
        "Nesse tema não consigo ajudar. O que faço: lembretes e listas. Também podes digitar /help para ver a lista de comandos, ou conversar por mensagem/áudio. ✨",
        "Isso fica fora da minha zona. Foco: organizar teu tempo. Digita /help para ver tudo; podes escrever ou mandar áudio.",
        "Adorava ajudar noutra coisa. Digita /help para ver a lista de comandos, ou fala por mensagem/áudio. 😊",
    ],
    "pt-BR": [
        "Esse assunto foge do que consigo fazer, mas adoraria ajudar em outra coisa! 😊 Organizo lembretes e listas. Você pode digitar /help para ver a lista de comandos, ou falar por mensagem ou áudio.",
        "Não tenho superpoderes para isso. Posso ajudar com lembretes e listas. Digite /help para ver os comandos; ou escreva/envie áudio.",
        "Nesse tema não consigo ajudar. O que faço: lembretes e listas. Você também pode digitar /help para ver a lista de comandos, ou conversar por mensagem/áudio. ✨",
        "Isso fica fora da minha área. Foco: organizar seu tempo. Digite /help para ver tudo; pode escrever ou mandar áudio.",
        "Adoraria ajudar em outra coisa. Digite /help para ver a lista de comandos, ou fale por mensagem/áudio. 😊",
    ],
    "es": [
        "Ese tema se sale de lo que puedo hacer, ¡pero me encantaría ayudarte! 😊 Organizo recordatorios y listas. Puedes escribir /help para ver la lista de comandos, o hablarme por mensaje o audio.",
        "No tengo superpoderes para eso. Ayudo con recordatorios y listas. Escribe /help para ver los comandos; o escribe/envía audio.",
        "En ese tema no puedo ayudar. Lo mío: recordatorios y listas. Puedes escribir /help para ver la lista de comandos, o conversar por mensaje/audio. ✨",
        "Eso se sale de mi zona. Foco: organizar tu tiempo. Escribe /help para ver todo; puedes escribir o mandar audio.",
        "Me encantaría ayudarte en otra cosa. Escribe /help para ver la lista de comandos, o háblame por mensaje/audio. 😊",
    ],
    "en": [
        "That's outside what I can do, but I'd love to help with something else! 😊 I do reminders and lists. You can type /help to see the list of commands, or message me / send audio.",
        "I don't have superpowers for that. I help with reminders and lists. Type /help to see the commands; or type/send audio.",
        "I can't help with that topic. What I do: reminders and lists. You can also type /help to see the list of commands, or chat by message/audio. ✨",
        "That's outside my lane. I focus on organising your time. Type /help to see everything; you can type or send audio.",
        "I'd love to help with something else. Type /help to see the list of commands, or message me / send audio. 😊",
    ],
}


# Nome do comando a mostrar no /help por idioma (canónico -> nome localizado)
COMMAND_DISPLAY_NAME: dict[LangCode, dict[str, str]] = {
    "pt-PT": {
        "/lembrete": "/lembrete",
        "/list": "/lista",
        "/hoje": "/hoje",
        "/semana": "/semana",
        "/agenda": "/agenda",
        "/timeline": "/linha",
        "/stats": "/estatísticas",
        "/resumo": "/resumo",
        "/recorrente": "/recorrente",
        "/meta": "/meta",
        "/metas": "/metas",
        "/pomodoro": "/pomodoro",
        "/tz": "/tz",
        "/lang": "/idioma",
        "/reset": "/reset",
        "/quiet": "/silêncio",
        "/feito": "/visto",
        "/remove": "/remover",
        "/hora": "/horas",
        "/data": "/data",
        "/evento": "/compromisso",
    },
    "pt-BR": {
        "/lembrete": "/lembrete",
        "/list": "/lista",
        "/hoje": "/hoje",
        "/semana": "/semana",
        "/agenda": "/agenda",
        "/timeline": "/linha",
        "/stats": "/estatísticas",
        "/resumo": "/resumo",
        "/recorrente": "/recorrente",
        "/meta": "/meta",
        "/metas": "/metas",
        "/pomodoro": "/pomodoro",
        "/tz": "/tz",
        "/lang": "/idioma",
        "/reset": "/reset",
        "/quiet": "/silêncio",
        "/feito": "/visto",
        "/remove": "/remover",
        "/hora": "/horas",
        "/data": "/data",
        "/evento": "/compromisso",
    },
    "es": {
        "/lembrete": "/recordatorio",
        "/list": "/lista",
        "/hoje": "/hoy",
        "/semana": "/semana",
        "/agenda": "/agenda",
        "/timeline": "/cronología",
        "/stats": "/estadísticas",
        "/resumo": "/resumen",
        "/recorrente": "/recurrente",
        "/meta": "/objetivo",
        "/metas": "/objetivos",
        "/pomodoro": "/pomodoro",
        "/tz": "/ciudad",
        "/lang": "/idioma",
        "/reset": "/reiniciar",
        "/quiet": "/silencio",
        "/pendente": "/pendiente",
        "/feito": "/hecho",
        "/remove": "/borrar",
        "/hora": "/hora",
        "/data": "/fecha",
        "/evento": "/evento",
    },
    "en": {
        "/lembrete": "/remind",
        "/list": "/list",
        "/hoje": "/today",
        "/semana": "/week",
        "/timeline": "/timeline",
        "/stats": "/stats",
        "/resumo": "/summary",
        "/recorrente": "/recurring",
        "/meta": "/goal",
        "/metas": "/goals",
        "/pomodoro": "/pomodoro",
        "/tz": "/timezone",
        "/lang": "/language",
        "/reset": "/reset",
        "/quiet": "/silent",
        "/feito": "/done",
        "/remove": "/remove",
        "/hora": "/time",
        "/data": "/date",
        "/evento": "/event",
    },
}


# /help — texto completo localizado; use {{/comando}} para o nome localizado (substituído por build_help)
HELP_FULL: dict[LangCode, str] = {
    "pt-PT": (
        "📋 *Todos os comandos:*\n\n"
        "*Comandos*\n"
        "• {{/lembrete}} — agendar (ex.: amanhã 9h; em 30 min)\n"
        "• {{/list}} — listas (compras, receitas, livros, músicas, notas, sites, coisas a fazer). Ex.: {{/list}} mercado add leite\n"
        "• {{/hoje}} — agenda e lembretes do dia  |  {{/semana}} — agenda da semana (só eventos)\n"
        "• {{/timeline}} — histórico (lembretes, tarefas, eventos)\n"
        "• {{/stats}} — estatísticas; {{/stats}} dia ou {{/stats}} semana\n"
        "• {{/resumo}} — resumo da semana; {{/resumo}} mes — resumo do mês\n"
        "• {{/recorrente}} — lembretes recorrentes (ex.: {{/recorrente}} beber água todo dia 8h)\n"
        "• {{/meta}} add Nome até DD/MM — metas com prazo; {{/metas}} para listar\n"
        "• {{/pomodoro}} — timer 25 min foco; {{/pomodoro}} stop para cancelar\n\n"
        "*Configuração*\n"
        "• {{/tz}} Cidade — definir fuso (ex.: {{/tz}} Lisboa)\n"
        "• {{/lang}} — idioma: pt-pt, pt-br, es, en\n"
        "• {{/reset}} — refazer cadastro (nome, cidade)\n"
        "• {{/quiet}} 22:00-08:00 — horário silencioso\n\n"
        "*Dicas*\n"
        '• 🎙️ *Áudio:* Podes enviar áudios para criar lembretes ou listas. Se quiseres que eu responda em áudio, basta dizer "manda áudio" ou "responde por voz".\n'
        '• Marcar item como feito: podes dizer por áudio ("pronto", "já fiz"), escrever texto ou usar emoji ("✓", "👍") — não precisas de comando.\n'
        '• Se as respostas parecerem estranhas por causa do histórico, usa {{/reset}} ou /reiniciar para limpar a conversa.'
    ),
    "pt-BR": (
        "📋 *Todos os comandos:*\n\n"
        "*Comandos*\n"
        "• {{/lembrete}} — agendar (ex.: amanhã 9h; em 30 min)\n"
        "• {{/list}} — listas (compras, receitas, livros, músicas, notas, sites, coisas a fazer). Ex.: {{/list}} mercado add leite\n"
        "• {{/hoje}} — agenda e lembretes do dia  |  {{/semana}} — agenda da semana (só eventos)\n"
        "• {{/timeline}} — histórico (lembretes, tarefas, eventos)\n"
        "• {{/stats}} — estatísticas; {{/stats}} dia ou {{/stats}} semana\n"
        "• {{/resumo}} — resumo da semana; {{/resumo}} mes — resumo do mês\n"
        "• {{/recorrente}} — lembretes recorrentes (ex.: {{/recorrente}} beber água todo dia 8h)\n"
        "• {{/meta}} add Nome até DD/MM — metas com prazo; {{/metas}} para listar\n"
        "• {{/pomodoro}} — timer 25 min foco; {{/pomodoro}} stop para cancelar\n\n"
        "*Configuração*\n"
        "• {{/tz}} Cidade — definir fuso (ex.: {{/tz}} São Paulo)\n"
        "• {{/lang}} — idioma: pt-pt, pt-br, es, en\n"
        "• {{/reset}} — refazer cadastro (nome, cidade)\n"
        "• {{/quiet}} 22:00-08:00 — horário silencioso\n\n"
        "*Dicas*\n"
        '• 🎙️ *Áudio:* Você pode enviar áudios para criar lembretes ou listas. Se quiser que eu responda em áudio, basta dizer "manda áudio" ou "responde por voz".\n'
        '• Marcar item como feito: você pode dizer por áudio ("pronto", "já fiz"), escrever texto ou usar emoji ("✓", "👍") — não precisa de comando.\n'
        '• Se as respostas parecerem estranhas por causa do histórico, use {{/reset}} ou /reiniciar para limpar a conversa.'
    ),
    "es": (
        "📋 *Todos los comandos:*\n\n"
        "*Comandos*\n"
        "• {{/lembrete}} — programar (ej.: mañana 9h; en 30 min)\n"
        "• {{/list}} — listas (compras, recetas, libros, música, notas, sitios, pendientes). Ej.: {{/list}} mercado add leche\n"
        "• {{/hoje}} — agenda y recordatorios del día  |  {{/semana}} — agenda de la semana (solo eventos)\n"
        "• {{/timeline}} — historial (recordatorios, tareas, eventos)\n"
        "• {{/stats}} — estadísticas; {{/stats}} día o {{/stats}} semana\n"
        "• {{/resumo}} — resumen de la semana; {{/resumo}} mes — resumen del mes\n"
        "• {{/recorrente}} — recordatorios recurrentes (ej.: {{/recorrente}} beber agua todo día 8h)\n"
        "• {{/meta}} add Nombre hasta DD/MM — objetivos con plazo; {{/metas}} para listar\n"
        "• {{/pomodoro}} — temporizador 25 min foco; {{/pomodoro}} stop para cancelar\n\n"
        "*Configuración*\n"
        "• {{/tz}} Ciudad — definir zona horaria (ej.: {{/tz}} Madrid)\n"
        "• {{/lang}} — idioma: pt-pt, pt-br, es, en\n"
        "• {{/reset}} — reiniciar registro (nombre, ciudad)\n"
        "• {{/quiet}} 22:00-08:00 — horario silencioso\n\n"
        "*Consejos*\n"
        '• 🎙️ *Audio:* Puedes enviar audios para crear recordatorios o listas. Si quieres que responda en audio, solo di "manda audio" o "responde por voz".\n'
        '• Marcar ítem como hecho: puedes decir por audio ("listo", "ya está"), escribir texto o usar emoji ("✓", "👍") — no necesitas comando.\n'
        '• Si las respuestas parecen extrañas debido al historial, usa {{/reset}} o /reiniciar para limpiar el chat.'
    ),
    "en": (
        "📋 *All commands:*\n\n"
        "*Commands*\n"
        "• {{/lembrete}} — schedule (e.g. tomorrow 9am; in 30 min)\n"
        "• {{/list}} — lists (shopping, recipes, books, music, notes, sites, to-dos). E.g.: {{/list}} market add milk\n"
        "• {{/hoje}} — agenda and reminders for today  |  {{/semana}} — week agenda only (events)\n"
        "• {{/timeline}} — history (reminders, tasks, events)\n"
        "• {{/stats}} — statistics; {{/stats}} day or {{/stats}} week\n"
        "• {{/resumo}} — week summary; {{/resumo}} month — month summary\n"
        "• {{/recorrente}} — recurring reminders (e.g. {{/recorrente}} drink water every day 8am)\n"
        "• {{/meta}} add Name until DD/MM — goals with deadline; {{/metas}} to list\n"
        "• {{/pomodoro}} — 25 min focus timer; {{/pomodoro}} stop to cancel\n\n"
        "*Settings*\n"
        "• {{/tz}} City — set timezone (e.g. {{/tz}} London)\n"
        "• {{/lang}} — language: pt-pt, pt-br, es, en\n"
        "• {{/reset}} — redo signup (name, city)\n"
        "• {{/quiet}} 22:00-08:00 — quiet hours\n\n"
        "*Tips*\n"
        '• 🎙️ *Audio:* You can send voice notes to create reminders or lists. If you want me to reply with audio, just say "send audio" or "reply with voice".\n'
        '• Mark item done: you can say by voice ("done", "finished"), type or use emoji ("✓", "👍") — no command needed.\n'
        '• If answers seem off due to conversation history, use {{/reset}} or /reiniciar to clear the chat.'
    ),
}


# Cabeçalho da segunda mensagem do /help (lista de comandos slash)
HELP_COMMANDS_HEADER: dict[LangCode, str] = {
    "pt-PT": "📌 *Comandos disponíveis:*",
    "pt-BR": "📌 *Comandos disponíveis:*",
    "es": "📌 *Comandos disponibles:*",
    "en": "📌 *Available commands:*",
}

# Ordem dos comandos a listar na segunda mensagem do /help (canónicos)
_HELP_COMMANDS_ORDER = (
    "/help", "/start", "/lembrete", "/list", "/hoje", "/semana", "/agenda", "/timeline",
    "/stats", "/resumo", "/recorrente", "/meta", "/metas", "/pomodoro",
    "/tz", "/lang", "/reset", "/quiet", "/pendente", "/feito", "/remove", "/hora", "/data", "/evento",
)


def build_help(lang: LangCode) -> str:
    """Devolve o texto completo do /help no idioma, com nomes de comandos localizados."""
    text = HELP_FULL.get(lang, HELP_FULL["en"])
    names = COMMAND_DISPLAY_NAME.get(lang, COMMAND_DISPLAY_NAME["en"])
    for canonical, display_name in names.items():
        text = text.replace("{{" + canonical + "}}", display_name)
    return text


def build_help_commands_list(lang: LangCode) -> str:
    """Devolve uma única mensagem com o cabeçalho e a lista de comandos slash no idioma (para enviar após o /help)."""
    header = HELP_COMMANDS_HEADER.get(lang, HELP_COMMANDS_HEADER["en"])
    names = COMMAND_DISPLAY_NAME.get(lang, COMMAND_DISPLAY_NAME["en"])
    lines = [header, ""]
    for canonical in _HELP_COMMANDS_ORDER:
        display = names.get(canonical, canonical)
        lines.append(display)
    return "\n".join(lines)


# Segunda vez que o cliente vê a agenda no mesmo dia: perguntar se já realizou e se quer remover
AGENDA_SECOND_VIEW_PROMPT: dict[LangCode, str] = {
    "pt-PT": "\n\nJá realizaste ou concluíste algum destes eventos? Queres que eu remova algum da agenda? Podes dizer qual (quais) para eu remover.",
    "pt-BR": "\n\nJá realizou ou concluiu algum desses eventos? Quer que eu remova algum da agenda? Pode dizer qual (quais) para eu remover.",
    "es": "\n\n¿Ya realizaste o concluiste alguno de estos eventos? ¿Quieres que quite alguno de la agenda? Puedes decir cuál (cuáles) para que lo quite.",
    "en": "\n\nHave you already done or completed any of these events? Do you want me to remove any from the agenda? You can say which one(s) for me to remove.",
}

# Quando há eventos no dia: oferecer criar lembrete antes do evento (ex.: 15 min antes)
AGENDA_OFFER_REMINDER: dict[LangCode, str] = {
    "pt-PT": "\n\nQueres que eu te lembre antes de algum destes eventos? (ex.: 15 min antes) Diz o nome do evento (ex.: \"jantar\") ou \"sim\" para o primeiro.",
    "pt-BR": "\n\nQuer que eu te lembre antes de algum desses eventos? (ex.: 15 min antes) Diga o nome do evento (ex.: \"jantar\") ou \"sim\" para o primeiro.",
    "es": "\n\n¿Quieres que te recuerde antes de alguno de estos eventos? (ej.: 15 min antes) Di el nombre del evento (ej.: \"cena\") o \"sí\" para el primero.",
    "en": "\n\nDo you want me to remind you before any of these events? (e.g. 15 min before) Say the event name (e.g. \"dinner\") or \"yes\" for the first one.",
}


# Fallback quando o agente não produz resposta (ex.: mensagem muito longa, stress test)
AGENT_NO_RESPONSE_FALLBACK: dict[LangCode, str] = {
    "pt-PT": "Desculpa, não consegui processar completamente. Podes reformular ou dividir em partes mais pequenas? Digita /help para ver a lista de comandos. Podes escrever ou enviar áudio. 😊",
    "pt-BR": "Desculpa, não consegui processar completamente. Pode reformular ou dividir em partes menores? Digite /help para ver a lista de comandos. Pode escrever ou enviar áudio. 😊",
    "es": "Lo siento, no pude procesar completamente. ¿Puedes reformular o dividir en partes más pequeñas? Escribe /help para ver la lista de comandos. Puedes escribir o enviar audio. 😊",
    "en": "Sorry, I couldn't process that fully. Can you rephrase or break it into smaller parts? Type /help to see the list of commands. You can type or send audio. 😊",
}


# Durante o onboarding: "Quer comunicar noutro idioma? Temos pt-PT, pt-BR, es, en." (legado)
ONBOARDING_LANGUAGE_QUESTION: dict[LangCode, str] = {
    "pt-PT": "Queres comunicar noutro idioma? Temos português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Diz o código ou o nome do idioma, ou 'não' para continuar. 😊",
    "pt-BR": "Quer comunicar em outro idioma? Temos português de Portugal (pt-PT), português do Brasil (pt-BR), espanhol (es) e inglês (en). Diga o código ou o nome do idioma, ou 'não' para continuar. 😊",
    "es": "¿Quieres comunicarte en otro idioma? Tenemos portugués de Portugal (pt-PT), portugués de Brasil (pt-BR), español (es) e inglés (en). Di el código o el nombre del idioma, o 'no' para seguir. 😊",
    "en": "Want to use another language? We have Portuguese from Portugal (pt-PT), Brazilian Portuguese (pt-BR), Spanish (es) and English (en). Say the code or language name, or 'no' to continue. 😊",
}

# Pergunta curta de idioma: default por número + sim/não/outro
_ONBOARDING_LANG_SIMPLE: dict[LangCode, str] = {
    "pt-PT": "Falar em português de Portugal? (sim / não / outro idioma: pt-BR, es, en)",
    "pt-BR": "Falar em português do Brasil? (sim / não / outro idioma: pt-PT, es, en)",
    "es": "¿Hablar en español? (sí / no / otro: pt-PT, pt-BR, en)",
    "en": "Speak in English? (yes / no / other: pt-PT, pt-BR, es)",
}


def get_onboarding_language_question_simple(default_lang: LangCode) -> str:
    """Pergunta curta de idioma com default inferido do número."""
    return _ONBOARDING_LANG_SIMPLE.get(default_lang, _ONBOARDING_LANG_SIMPLE["en"])


def onboarding_progress_suffix(step: int, total: int = 4) -> str:
    """Sufixo de progresso para perguntas do onboarding, ex: ' [2/4]'."""
    return f" [{step}/{total}]"


# Lembrete sem conteúdo: pedir clarificação (ex.: "lembrete amanhã 10h" sem dizer o quê)
REMINDER_ASK_WHAT: dict[LangCode, str] = {
    "pt-PT": "De que é o lembrete? Por exemplo: ir à farmácia, tomar o remédio, reunião com o João, buscar as crianças...",
    "pt-BR": "De que é o lembrete? Por exemplo: ir à farmácia, tomar o remédio, reunião com o João, buscar as crianças...",
    "es": "¿De qué es el recordatorio? Por ejemplo: ir a la farmacia, tomar la medicina, reunión con Juan...",
    "en": "What's the reminder for? E.g.: go to the pharmacy, take medicine, meeting with John, pick up the kids...",
}

# Horário pedido já passou hoje (evita agendar para o ano seguinte e avisa)
REMINDER_TIME_PAST_TODAY: dict[LangCode, str] = {
    "pt-PT": "Esse horário já passou hoje. Queres que eu agende para amanhã à mesma hora?",
    "pt-BR": "Esse horário já passou hoje. Quer que eu agende para amanhã à mesma hora?",
    "es": "Esa hora ya pasó hoy. ¿Quieres que lo programe para mañana a la misma hora?",
    "en": "That time has already passed today. Should I schedule it for tomorrow at the same time?",
}

# Data inteira no passado: avisar e pedir confirmação para agendar no ano seguinte
REMINDER_DATE_PAST_ASK_NEXT_YEAR: dict[LangCode, str] = {
    "pt-PT": "Essa data já passou. Queres que eu agende para o ano que vem à mesma data e hora? (1=sim 2=não)",
    "pt-BR": "Essa data já passou. Quer que eu agende para o ano que vem à mesma data e hora? (1=sim 2=não)",
    "es": "Esa fecha ya pasó. ¿Quieres que lo programe para el año que viene a la misma fecha y hora? (1=sí 2=no)",
    "en": "That date has already passed. Should I schedule it for next year at the same date and time? (1=yes 2=no)",
}
REMINDER_DATE_PAST_SCHEDULED: dict[LangCode, str] = {
    "pt-PT": "Registado para o ano que vem. ✨",
    "pt-BR": "Registrado para o ano que vem. ✨",
    "es": "Programado para el año que viene. ✨",
    "en": "Scheduled for next year. ✨",
}

# Lembretes removidos por estarem no passado (bug/API): desculpa e compromisso
STALE_REMOVAL_APOLOGY: dict[LangCode, str] = {
    "pt-PT": "Peço desculpa: removi {count} lembrete(s) que estavam no passado e não deviam estar na lista: {removed_list}. Já aprendi com isto e o erro não se vai repetir. 🙏",
    "pt-BR": "Sinto muito: removi {count} lembrete(s) que estavam no passado e não deveriam estar na lista: {removed_list}. Já aprendi com isso e o erro não vai se repetir. 🙏",
    "es": "Lo siento: he eliminado {count} recordatorio(s) que estaban en el pasado y no deberían estar en la lista: {removed_list}. Ya he aprendido y el error no se repetirá. 🙏",
    "en": "I'm sorry: I removed {count} reminder(s) that were in the past and shouldn't have been in the list: {removed_list}. I've learned from this and the error won't happen again. 🙏",
}

# Data vaga: pedir dia (ex.: "médico às 10h" → "Que dia é a consulta?")
REMINDER_ASK_DATE_CONSULTA: dict[LangCode, str] = {
    "pt-PT": "Que dia é a tua consulta? Amanhã? Hoje? Segunda?",
    "pt-BR": "Que dia é a sua consulta? Amanhã? Hoje? Segunda?",
    "es": "¿Qué día es tu cita? ¿Mañana? ¿Hoy? ¿Lunes?",
    "en": "What day is your appointment? Tomorrow? Today? Monday?",
}
REMINDER_ASK_DATE_GENERIC: dict[LangCode, str] = {
    "pt-PT": "Que dia é? Amanhã? Hoje? Segunda?",
    "pt-BR": "Que dia é? Amanhã? Hoje? Segunda?",
    "es": "¿Qué día es? ¿Mañana? ¿Hoy? ¿Lunes?",
    "en": "What day is it? Tomorrow? Today? Monday?",
}

# Horário vago: pedir hora (ex.: "tenho consulta amanhã" → "A que horas é a sua consulta?")
REMINDER_ASK_TIME_CONSULTA: dict[LangCode, str] = {
    "pt-PT": "A que horas é a tua consulta?",
    "pt-BR": "A que horas é a sua consulta?",
    "es": "¿A qué hora es tu cita?",
    "en": "What time is your appointment?",
}
REMINDER_ASK_TIME_GENERIC: dict[LangCode, str] = {
    "pt-PT": "A que horas é?",
    "pt-BR": "A que horas é?",
    "es": "¿A qué hora es?",
    "en": "What time is it?",
}

# Preferência de antecedência
# Após registar evento na agenda (data+hora completos): perguntar se quer lembrete
EVENT_REGISTERED_ASK_REMINDER: dict[LangCode, str] = {
    "pt-PT": "Registado na agenda. Queres que eu te lembre na hora (ou com antecedência)?",
    "pt-BR": "Registrado na agenda. Quer que eu te lembre na hora (ou com antecedência)?",
    "es": "Registrado en la agenda. ¿Quieres que te avise a la hora (o con antelación)?",
    "en": "Added to your agenda. Do you want me to remind you at the time (or in advance)?",
}

REMINDER_ASK_ADVANCE_PREFERENCE: dict[LangCode, str] = {
    "pt-PT": "Queres ser lembrado com antecedência ou apenas na hora do evento?",
    "pt-BR": "Quer ser lembrado com antecedência ou apenas na hora do evento?",
    "es": "¿Quieres que te avise con antelación o solo a la hora del evento?",
    "en": "Do you want to be reminded in advance or just at the event time?",
}

# Quanto tempo antes
REMINDER_ASK_ADVANCE_AMOUNT: dict[LangCode, str] = {
    "pt-PT": "Quanto tempo antes? Por ex.: 30 min, 1 hora...",
    "pt-BR": "Quanto tempo antes? Por ex.: 30 min, 1 hora...",
    "es": "¿Cuánto tiempo antes? Ej.: 30 min, 1 hora...",
    "en": "How long before? E.g.: 30 min, 1 hour...",
}

# Cliente disse que não quer lembrete — confirmação curta
EVENT_REGISTERED_NO_REMINDER: dict[LangCode, str] = {
    "pt-PT": "Ok, registado na agenda. Sem lembrete. 😊",
    "pt-BR": "Ok, registrado na agenda. Sem lembrete. 😊",
    "es": "Ok, registrado en la agenda. Sin recordatorio. 😊",
    "en": "Ok, added to your agenda. No reminder. 😊",
}

# Nudge proativo 12h antes (quando não pediu lembrete mas o evento é importante). {event_name} = nome do evento
PROACTIVE_NUDGE_12H_MSG: dict[LangCode, str] = {
    "pt-PT": "🫶 Sei que não pediste para eu lembrar, mas sou um robô proativo e acho que este evento é especial: *{event_name}*. Não te esqueças! 😊",
    "pt-BR": "🫶 Sei que você não pediu para eu lembrar, mas sou um robô proativo e acho que esse evento é importante: *{event_name}*. Não esqueça! 😊",
    "es": "🫶 Sé que no pediste que te recordara, pero soy un robot proactivo y me parece que este evento es especial: *{event_name}*. ¡No lo olvides! 😊",
    "en": "🫶 I know you didn't ask me to remind you, but I'm a proactive robot and this event seems special to me: *{event_name}*. Don't forget! 😊",
}

# Resposta inválida — insistir (X de 3 tentativas)
REMINDER_ASK_AGAIN: dict[LangCode, str] = {
    "pt-PT": "Não percebi. Tenta novamente — preciso de evento, data e hora para registrar.",
    "pt-BR": "Não entendi. Tente novamente — preciso do evento, data e hora para registrar.",
    "es": "No entendí. Intenta de nuevo — necesito evento, fecha y hora para registrar.",
    "en": "I didn't get that. Try again — I need event, date and time to register.",
}
REMINDER_RETRY_SUFFIX: dict[LangCode, str] = {
    "pt-PT": " ({n} de 3 tentativas)",
    "pt-BR": " ({n} de 3 tentativas)",
    "es": " ({n} de 3 intentos)",
    "en": " ({n} of 3 attempts)",
}

# Dica quando o timezone não foi informado pelo cliente (para acertar sempre o horário)
TZ_HINT_SET_CITY: dict[LangCode, str] = {
    "pt-PT": "💡 Para garantir que os lembretes são à tua hora: /tz Cidade (ex.: /tz Lisboa).",
    "pt-BR": "💡 Para garantir que os lembretes sejam no seu horário: /tz Cidade (ex.: /tz São Paulo).",
    "es": "💡 Para que los recordatorios sean a tu hora: /tz Ciudad (ej.: /tz Madrid).",
    "en": "💡 To have reminders at your local time: /tz City (e.g. /tz New York).",
}

# Evento recorrente: confirmação simpática
RECURRING_EVENT_CONFIRM: dict[LangCode, str] = {
    "pt-PT": "Parece que {event} é um evento recorrente! Queres que eu registe para {schedule}? 😊",
    "pt-BR": "Parece que {event} é um evento recorrente! Quer que eu registe para {schedule}? 😊",
    "es": "¡Parece que {event} es un evento recurrente! ¿Quieres que lo registre para {schedule}? 😊",
    "en": "It looks like {event} is a recurring event! Shall I register it for {schedule}? 😊",
}

# Resposta inválida em "até quando" — insistir
RECURRING_ASK_END_DATE_AGAIN: dict[LangCode, str] = {
    "pt-PT": "Não percebi. Indefinido/para sempre, fim da semana, ou fim do mês?",
    "pt-BR": "Não entendi. Indefinido/para sempre, fim da semana, ou fim do mês?",
    "es": "No entendí. ¿Indefinido/para siempre, fin de semana o fin de mes?",
    "en": "I didn't get that. Indefinite/forever, end of week, or end of month?",
}

# Até quando dura o evento recorrente
RECURRING_ASK_END_DATE: dict[LangCode, str] = {
    "pt-PT": "Até quando dura? (ex: indefinido/para sempre, fim da semana, fim do mês, ou diz a data)",
    "pt-BR": "Até quando dura? (ex: indefinido/para sempre, fim da semana, fim do mês, ou diga a data)",
    "es": "¿Hasta cuándo dura? (ej: indefinido/para siempre, fin de semana, fin de mes, o di la fecha)",
    "en": "Until when does it last? (e.g. indefinite/forever, end of week, end of month, or give the date)",
}

# Confirmação após registo
RECURRING_REGISTERED: dict[LangCode, str] = {
    "pt-PT": "Registado! ✨ Lembrete recorrente para {event} ({schedule}). Podes remover quando quiseres com 👎, /lembrete ou pedindo ao assistente.",
    "pt-BR": "Registrado! ✨ Lembrete recorrente para {event} ({schedule}). Pode remover quando quiser com 👎, /lembrete ou pedindo ao assistente.",
    "es": "¡Registrado! ✨ Recordatorio recurrente para {event} ({schedule}). Puedes eliminarlo cuando quieras con 👎, /lembrete o pidiendo al asistente.",
    "en": "Registered! ✨ Recurring reminder for {event} ({schedule}). You can remove it anytime with 👎, /lembrete or by asking the assistant.",
}

RECURRING_REGISTERED_UNTIL: dict[LangCode, str] = {
    "pt-PT": "Registado até {end}! ✨ Lembrete recorrente para {event} ({schedule}). Podes remover com 👎, /lembrete ou pedindo ao assistente.",
    "pt-BR": "Registrado até {end}! ✨ Lembrete recorrente para {event} ({schedule}). Pode remover com 👎, /lembrete ou pedindo ao assistente.",
    "es": "¡Registrado hasta {end}! ✨ Recordatorio recurrente para {event} ({schedule}). Puedes eliminar con 👎, /lembrete o pidiendo al asistente.",
    "en": "Registered until {end}! ✨ Recurring reminder for {event} ({schedule}). Remove with 👎, /lembrete or by asking the assistant.",
}

# Desistiu — não registrou por falta de informação
REMINDER_FAILED_NO_INFO: dict[LangCode, str] = {
    "pt-PT": "Não consegui registrar o lembrete por falta de informação. Preciso do evento, data e hora. Quando tiver os três, pode tentar de novo.",
    "pt-BR": "Não consegui registrar o lembrete por falta de informação. Preciso do evento, data e hora. Quando tiver os três, pode tentar novamente.",
    "es": "No pude registrar el recordatorio por falta de información. Necesito evento, fecha y hora. Cuando tengas los tres, puedes intentar de nuevo.",
    "en": "I couldn't register the reminder due to lack of information. I need event, date and time. When you have all three, you can try again.",
}

# Mensagem quando resposta é inválida: repetir ou oferecer pular
ONBOARDING_INVALID_RESPONSE: dict[LangCode, str] = {
    "pt-PT": "Não percebi. Responde à pergunta ou diz 'pular' para avançar.",
    "pt-BR": "Não entendi. Responda à pergunta ou diga 'pular' para avançar.",
    "es": "No entendí. Responde la pregunta o di 'saltar' para seguir.",
    "en": "I didn't get that. Answer the question or say 'skip' to continue.",
}


# Afirmativos que indicam "continuar no idioma sugerido" (sim/yes = aceitar)
# "não" = quer outro idioma → deve especificar qual
_AFFIRMATIVE_KEEP_PATTERNS = (
    r"^(sim|yes|s[ií]|s[ií][ií]|ok|okay|claro|pode\s+ser|tudo\s+bem|bom|bem)\s*\.*$",
    r"^(y|ye|yep|yeah|ya)\s*\.*$",
)
_AFFIRMATIVE_RE = re.compile("|".join(_AFFIRMATIVE_KEEP_PATTERNS), re.I)


def parse_onboarding_language_response(
    message: str,
    phone_for_locale: str | None = None,
) -> Literal["keep"] | LangCode | None:
    """
    Interpreta resposta à pergunta de idioma no onboarding.
    - "keep": sim/não/ok → continuar com idioma sugerido (do número)
    - LangCode: escolha explícita (pt-PT, pt-BR, es, en)
    - None: inválido ou ambíguo (repetir pergunta ou oferecer pular)
    """
    if not message or not message.strip():
        return None
    t = message.strip().lower()
    if len(t) > 80:  # Resposta longa demais para escolha simples
        return None
    # Escolha explícita de idioma tem prioridade (português genérico infere do número)
    chosen = parse_language_switch_request(message, phone_for_locale)
    if chosen:
        return chosen
    # Afirmativos curtos = manter
    if _AFFIRMATIVE_RE.search(t):
        return "keep"
    return None

# Intervalo mínimo para lembretes recorrentes
REMINDER_MIN_INTERVAL_30MIN: dict[LangCode, str] = {
    "pt-PT": "O intervalo mínimo para lembretes recorrentes é 30 minutos. Ex.: a cada 30 min ou a cada 1 hora.",
    "pt-BR": "O intervalo mínimo para lembretes recorrentes é 30 minutos. Ex.: a cada 30 min ou a cada 1 hora.",
    "es": "El intervalo mínimo para recordatorios recurrentes es 30 minutos. Ej.: cada 30 min o cada 1 hora.",
    "en": "The minimum interval for recurring reminders is 30 minutes. E.g. every 30 min or every 1 hour.",
}
REMINDER_MIN_INTERVAL_2H: dict[LangCode, str] = {
    "pt-PT": "O intervalo mínimo para lembretes recorrentes é 2 horas. Ex.: a cada 2 horas ou a cada 3 horas.",
    "pt-BR": "O intervalo mínimo para lembretes recorrentes é 2 horas. Ex.: a cada 2 horas ou a cada 3 horas.",
    "es": "El intervalo mínimo para recordatorios recurrentes es 2 horas. Ej.: cada 2 horas o cada 3 horas.",
    "en": "The minimum interval for recurring reminders is 2 hours. E.g. every 2 hours or every 3 hours.",
}
# Limites por dia: 40 agenda, 40 lembretes, 80 total (aviso aos 70%)
LIMIT_AGENDA_PER_DAY_REACHED: dict[LangCode, str] = {
    "pt-PT": "Atingiste o limite de 40 eventos de agenda para este dia. Remove alguns da agenda antes de adicionar mais.",
    "pt-BR": "Você atingiu o limite de 40 eventos de agenda para este dia. Remova alguns da agenda antes de adicionar mais.",
    "es": "Has alcanzado el límite de 40 eventos de agenda para este día. Elimina algunos antes de añadir más.",
    "en": "You've reached the limit of 40 agenda events for this day. Remove some from your agenda before adding more.",
}
LIMIT_REMINDERS_PER_DAY_REACHED: dict[LangCode, str] = {
    "pt-PT": "Atingiste o limite de 40 lembretes para este dia. Remove alguns com 👎 ou /lembrete antes de adicionar mais.",
    "pt-BR": "Você atingiu o limite de 40 lembretes para este dia. Remova alguns com 👎 ou /lembrete antes de adicionar mais.",
    "es": "Has alcanzado el límite de 40 recordatorios para este día. Elimina algunos con 👎 o /lembrete antes de añadir más.",
    "en": "You've reached the limit of 40 reminders for this day. Remove some with 👎 or /lembrete before adding more.",
}
LIMIT_TOTAL_PER_DAY_REACHED: dict[LangCode, str] = {
    "pt-PT": "Atingiste o limite de 80 itens (agenda + lembretes) para este dia. Remove alguns antes de adicionar mais.",
    "pt-BR": "Você atingiu o limite de 80 itens (agenda + lembretes) para este dia. Remova alguns antes de adicionar mais.",
    "es": "Has alcanzado el límite de 80 ítems (agenda + recordatorios) para este día. Elimina algunos antes de añadir más.",
    "en": "You've reached the limit of 80 items (agenda + reminders) for this day. Remove some before adding more.",
}
LIMIT_WARNING_70: dict[LangCode, str] = {
    "pt-PT": "Estás a 70% do limite diário (40 eventos de agenda, 40 lembretes, 80 no total). Convém não ultrapassar.",
    "pt-BR": "Você está em 70% do limite diário (40 eventos de agenda, 40 lembretes, 80 no total). Convém não ultrapassar.",
    "es": "Estás al 70% del límite diario (40 eventos de agenda, 40 recordatorios, 80 en total). Conviene no superar.",
    "en": "You're at 70% of the daily limit (40 agenda events, 40 reminders, 80 total). Best not to exceed it.",
}
REMINDER_LIMIT_EXCEEDED: dict[LangCode, str] = {
    "pt-PT": "Tens o limite máximo de 40 lembretes para este dia. Remove alguns com 👎 ou /lembrete antes de adicionar mais.",
    "pt-BR": "Você atingiu o limite de 40 lembretes para este dia. Remova alguns com 👎 ou /lembrete antes de adicionar mais.",
    "es": "Has alcanzado el límite de 40 recordatorios para este día. Elimina algunos con 👎 o /lembrete antes de añadir más.",
    "en": "You've reached the limit of 40 reminders for this day. Remove some with 👎 or /lembrete before adding more.",
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


def parse_language_switch_request(
    message: str,
    phone_for_locale: str | None = None,
) -> LangCode | None:
    """
    Detecta se a mensagem é um pedido explícito para falar noutro idioma (pt-PT, pt-BR, es, en).
    Retorna o código do idioma pedido ou None.

    Para "fale em português" (genérico): infere pt-PT vs pt-BR pelo número (351→pt-PT, 55→pt-BR).
    Em qualquer pedido explícito de pt-PT, pt-BR, es ou en, altera imediatamente para essa língua.
    """
    if not message or not message.strip():
        return None
    text = message.strip()
    try:
        text = unicodedata.normalize("NFC", text)
    except Exception:
        pass
    # Lista de termos de negação/paragem (anti-switch)
    negative_terms = [
        "não", "nao", "no ", "don't", "stop", "para de ", "para com ", "chega", "never", "nunca",
        "quite", "salir", "cancel", "errado", "incorreto"
    ]
    
    for pattern, lang in _LANG_SWITCH_PATTERNS:
        match = pattern.search(text)
        if match:
            # Check for negation in the context (around the match or in the whole short message)
            context = text.lower()
            # Se for uma frase curta e contiver negação, provavelmente é um "não mude" ou "não fale"
            if any(neg in context for neg in negative_terms):
                # Se a negação estiver próxima (ex: "não fala em espanhol"), ignorar o switch
                # mas permitir se for "não fale espanhol, fale português" (complexo, melhor LLM)
                if len(context) < 40:
                    continue
            
            if lang == "pt":  # Genérico: inferir do número
                if phone_for_locale:
                    inferred = phone_to_default_language(phone_for_locale)
                    return "pt-PT" if inferred == "pt-PT" else "pt-BR"
                return "pt-BR"
            return lang
    return None


# ---------------------------------------------------------------------------
# cron.py tool response strings
# ---------------------------------------------------------------------------

CRON_REMINDER_SCHEDULED: dict[LangCode, str] = {
    "pt-PT": "Lembrete agendado (id: {job_id}).",
    "pt-BR": "Lembrete agendado (id: {job_id}).",
    "es": "Recordatorio programado (id: {job_id}).",
    "en": "Reminder scheduled (id: {job_id}).",
}

CRON_PRE_REMINDERS_ADDED: dict[LangCode, str] = {
    "pt-PT": " + {count} aviso(s) antes do evento (conforme as tuas preferências).",
    "pt-BR": " + {count} aviso(s) antes do evento (conforme as suas preferências).",
    "es": " + {count} aviso(s) antes del evento (según tus preferencias).",
    "en": " + {count} reminder(s) before the event (according to your preferences).",
}

CRON_UNCONFIRMED_RETRY: dict[LangCode, str] = {
    "pt-PT": " Se não confirmares com 👍, relembro em {minutes} min.",
    "pt-BR": " Se não confirmar com 👍, relembro em {minutes} min.",
    "es": " Si no confirmas con 👍, te recuerdo en {minutes} min.",
    "en": " If you don't confirm with 👍, I'll remind you again in {minutes} min.",
}

CRON_DEPENDS_ON: dict[LangCode, str] = {
    "pt-PT": " Dispara depois de marcares \"{job_id}\" como feito.",
    "pt-BR": " Dispara depois de você marcar \"{job_id}\" como feito.",
    "es": " Se activa después de que marques \"{job_id}\" como hecho.",
    "en": " Triggers after you mark \"{job_id}\" as done.",
}

CRON_WILL_BE_SENT: dict[LangCode, str] = {
    "pt-PT": " Será enviado às {time} ({tz}). Mantém o Zapista ligado para receberes a notificação. Se não receberes à hora indicada, verifica em /definições o horário silencioso.",
    "pt-BR": " Será enviado às {time} ({tz}). Mantenha o Zapista ligado para receber a notificação. Se não receber no horário indicado, verifique em /definições o horário silencioso.",
    "es": " Se enviará a las {time} ({tz}). Mantén Zapista abierto para recibir la notificación. Si no la recibes, revisa el horario silencioso en /definições.",
    "en": " Will be sent at {time} ({tz}). Keep Zapista running to receive the notification. If you don't get it, check the quiet hours in /settings.",
}

CRON_CREATED_BY_CLI: dict[LangCode, str] = {
    "pt-PT": " (Criado pelo terminal; para receber no WhatsApp, envia o lembrete pelo próprio WhatsApp.)",
    "pt-BR": " (Criado pelo terminal; para receber no WhatsApp, envie o lembrete pelo próprio WhatsApp.)",
    "es": " (Creado desde la terminal; para recibirlo en WhatsApp, envía el recordatorio desde el propio WhatsApp.)",
    "en": " (Created from the terminal; to receive it on WhatsApp, send the reminder through WhatsApp itself.)",
}

CRON_TZ_LABEL_FROM_PHONE: dict[LangCode, str] = {
    "pt-PT": "no teu fuso",
    "pt-BR": "no seu fuso",
    "es": "en tu zona horaria",
    "en": "your timezone",
}

CRON_TZ_LABEL_UTC_FALLBACK: dict[LangCode, str] = {
    "pt-PT": "UTC (configura /tz para ver no teu fuso)",
    "pt-BR": "UTC (configure /tz para ver no seu fuso)",
    "es": "UTC (configura /tz para ver en tu zona horaria)",
    "en": "UTC (set /tz to see it in your timezone)",
}

CRON_NO_REMINDERS: dict[LangCode, str] = {
    "pt-PT": "Nenhum lembrete agendado.",
    "pt-BR": "Nenhum lembrete agendado.",
    "es": "No hay recordatorios programados.",
    "en": "No reminders scheduled.",
}

CRON_REMINDERS_HEADER: dict[LangCode, str] = {
    "pt-PT": "Lembretes agendados:",
    "pt-BR": "Lembretes agendados:",
    "es": "Recordatorios programados:",
    "en": "Scheduled reminders:",
}

CRON_REMOVED: dict[LangCode, str] = {
    "pt-PT": "Removido: {job_id}",
    "pt-BR": "Removido: {job_id}",
    "es": "Eliminado: {job_id}",
    "en": "Removed: {job_id}",
}

CRON_JOB_NOT_FOUND: dict[LangCode, str] = {
    "pt-PT": "Job {job_id} não encontrado.",
    "pt-BR": "Job {job_id} não encontrado.",
    "es": "Tarea {job_id} no encontrada.",
    "en": "Job {job_id} not found.",
}

CRON_JOB_NOT_FOUND_DELIVERED: dict[LangCode, str] = {
    "pt-PT": "Job {job_id} não está na lista (lembretes únicos são removidos após disparar). O último lembrete entregue foi em {delivered_at}. Use 'rever lembretes' para ver o histórico completo.",
    "pt-BR": "Job {job_id} não está na lista (lembretes únicos são removidos após disparar). O último lembrete entregue foi em {delivered_at}. Use 'rever lembretes' para ver o histórico completo.",
    "es": "La tarea {job_id} no está en la lista (los recordatorios únicos se eliminan al disparar). El último recordatorio entregado fue el {delivered_at}. Usa 'rever lembretes' para ver el historial completo.",
    "en": "Job {job_id} is not in the list (one-time reminders are removed after firing). The last delivered reminder was at {delivered_at}. Use 'rever lembretes' to see the full history.",
}

CRON_JOB_NOT_FOUND_MAYBE_FIRED: dict[LangCode, str] = {
    "pt-PT": "Job {job_id} não encontrado. Se era um lembrete único, pode já ter sido executado. Use 'rever lembretes' para ver o histórico.",
    "pt-BR": "Job {job_id} não encontrado. Se era um lembrete único, pode já ter sido executado. Use 'rever lembretes' para ver o histórico.",
    "es": "Tarea {job_id} no encontrada. Si era un recordatorio único, puede que ya se haya ejecutado. Usa 'rever lembretes' para ver el historial.",
    "en": "Job {job_id} not found. If it was a one-time reminder, it may have already fired. Use 'rever lembretes' to see the history.",
}

CRON_JOB_NOT_YOURS: dict[LangCode, str] = {
    "pt-PT": "Job {job_id} não te pertence.",
    "pt-BR": "Job {job_id} não te pertence.",
    "es": "La tarea {job_id} no te pertenece.",
    "en": "Job {job_id} does not belong to you.",
}

# ---------------------------------------------------------------------------
# event_tool.py response strings
# ---------------------------------------------------------------------------

EVENT_ADDED: dict[LangCode, str] = {
    "pt-PT": "Anotado: {tipo} '{name}'{date_msg} (id: {id})",
    "pt-BR": "Anotado: {tipo} '{name}'{date_msg} (id: {id})",
    "es": "Anotado: {tipo} '{name}'{date_msg} (id: {id})",
    "en": "Noted: {tipo} '{name}'{date_msg} (id: {id})",
}

EVENT_REQUIRES_DATE: dict[LangCode, str] = {
    "pt-PT": "Evento de agenda exige data! Por favor fornece uma data/hora.",
    "pt-BR": "Evento de agenda exige data! Por favor forneça uma data/hora.",
    "es": "¡El evento de agenda requiere fecha! Por favor proporciona una fecha/hora.",
    "en": "Agenda event requires a date! Please provide a date/time.",
}

EVENT_NONE_FOUND: dict[LangCode, str] = {
    "pt-PT": "Nenhum {tipo}.",
    "pt-BR": "Nenhum {tipo}.",
    "es": "Ningún {tipo}.",
    "en": "No {tipo} found.",
}

EVENT_CALENDAR_IMPORTED: dict[LangCode, str] = {
    "pt-PT": " (importado do calendário)",
    "pt-BR": " (importado do calendário)",
    "es": " (importado del calendario)",
    "en": " (imported from calendar)",
}

EVENT_REMOVE_NOT_FOUND: dict[LangCode, str] = {
    "pt-PT": "Nenhum evento de hoje com \"{name}\" na agenda.",
    "pt-BR": "Nenhum evento de hoje com \"{name}\" na agenda.",
    "es": "Ningún evento de hoy con \"{name}\" en la agenda.",
    "en": "No event today with \"{name}\" in the agenda.",
}

EVENT_REMOVE_MULTIPLE: dict[LangCode, str] = {
    "pt-PT": "Vários eventos coincidem. Especifica: {names}",
    "pt-BR": "Vários eventos coincidem. Especifica: {names}",
    "es": "Varios eventos coinciden. Especifica: {names}",
    "en": "Multiple events match. Specify: {names}",
}

EVENT_REMOVED: dict[LangCode, str] = {
    "pt-PT": "Removido da agenda: \"{name}\".",
    "pt-BR": "Removido da agenda: \"{name}\".",
    "es": "Eliminado de la agenda: \"{name}\".",
    "en": "Removed from agenda: \"{name}\".",
}

# ---------------------------------------------------------------------------
# list_tool.py response strings
# ---------------------------------------------------------------------------

LIST_EMPTY_ITEM_ERROR: dict[LangCode, str] = {
    "pt-PT": "Para criar ou adicionar à lista '{list_name}', preciso de pelo menos um item! Qual item queres adicionar?",
    "pt-BR": "Para criar ou adicionar à lista '{list_name}', preciso de pelo menos um item! Qual item deseja adicionar?",
    "es": "Para crear o añadir a la lista '{list_name}', ¡necesito al menos un ítem! ¿Qué ítem quieres añadir?",
    "en": "To create or add to the list '{list_name}', I need at least one item! What item would you like to add?",
}

# ---------------------------------------------------------------------------
# confirm_actions.py response strings
# ---------------------------------------------------------------------------

CONFIRM_LIST_CREATED: dict[LangCode, str] = {
    "pt-PT": "✅ Lista *hoje* criada com {count} afazeres. Usa /list hoje para ver.",
    "pt-BR": "✅ Lista *hoje* criada com {count} afazeres. Use /list hoje para ver.",
    "es": "✅ Lista *hoy* creada con {count} tareas. Usa /list hoy para verla.",
    "en": "✅ List *today* created with {count} to-dos. Use /list today to see it.",
}

CONFIRM_NO_ITEMS: dict[LangCode, str] = {
    "pt-PT": "Nenhum item para adicionar.",
    "pt-BR": "Nenhum item para adicionar.",
    "es": "Ningún ítem para añadir.",
    "en": "No items to add.",
}

CONFIRM_REMINDERS_HINT: dict[LangCode, str] = {
    "pt-PT": "Para lembretes, podes usar /lembrete para cada atividade com horário. Ex.: /lembrete ir à escola amanhã 8h. Ou diz-me quando queres ser lembrado e eu ajudo.",
    "pt-BR": "Para lembretes, você pode usar /lembrete para cada atividade com horário. Ex.: /lembrete ir à escola amanhã 8h. Ou diga quando quer ser lembrado e eu ajudo.",
    "es": "Para recordatorios, puedes usar /lembrete para cada actividad con horario. Ej.: /lembrete ir al colegio mañana 8h. O dime cuándo quieres que te recuerde y te ayudo.",
    "en": "For reminders, you can use /lembrete for each activity with a time. E.g.: /lembrete go to school tomorrow 8am. Or tell me when you want to be reminded and I'll help.",
}

CONFIRM_LIST_AND_REMINDERS: dict[LangCode, str] = {
    "pt-PT": "✅ Lista *hoje* criada com {count} itens. Para lembretes: usa /lembrete para cada um (ex.: /lembrete ir à escola amanhã 8h) ou diz quando queres ser lembrado.",
    "pt-BR": "✅ Lista *hoje* criada com {count} itens. Para lembretes: use /lembrete para cada um (ex.: /lembrete ir à escola amanhã 8h) ou diga quando quer ser lembrado.",
    "es": "✅ Lista *hoy* creada con {count} ítems. Para recordatorios: usa /lembrete para cada uno (ej.: /lembrete ir al colegio mañana 8h) o di cuándo quieres que te recuerde.",
    "en": "✅ List *today* created with {count} items. For reminders: use /lembrete for each one (e.g.: /lembrete go to school tomorrow 8am) or say when you'd like to be reminded.",
}

CONFIRM_RECIPE_LIST_CREATED: dict[LangCode, str] = {
    "pt-PT": "Lista criada! 🛒 *{list_name}* com {count} itens baseados na receita:",
    "pt-BR": "Lista criada! 🛒 *{list_name}* com {count} itens baseados na receita:",
    "es": "¡Lista creada! 🛒 *{list_name}* con {count} ítems basados en la receta:",
    "en": "List created! 🛒 *{list_name}* with {count} items based on the recipe:",
}

CONFIRM_RECIPE_NO_INGREDIENTS: dict[LangCode, str] = {
    "pt-PT": "Não consegui extrair os ingredientes. Tenta de novo com outra receita.",
    "pt-BR": "Não consegui extrair os ingredientes. Tente de novo com outra receita.",
    "es": "No pude extraer los ingredientes. Intenta de nuevo con otra receta.",
    "en": "I couldn't extract the ingredients. Try again with another recipe.",
}

CONFIRM_RECIPE_CANCEL: dict[LangCode, str] = {
    "pt-PT": "Ok, lista de compras cancelada.",
    "pt-BR": "Ok, lista de compras cancelada.",
    "es": "Ok, lista de compras cancelada.",
    "en": "Ok, shopping list cancelled.",
}

CONFIRM_DATE_PAST_CANCEL: dict[LangCode, str] = {
    "pt-PT": "Ok, não agendei. Quando quiseres, diz a data e hora de novo.",
    "pt-BR": "Ok, não agendei. Quando quiser, diga a data e hora de novo.",
    "es": "Ok, no lo programé. Cuando quieras, dime la fecha y hora de nuevo.",
    "en": "Ok, I didn't schedule it. Whenever you're ready, give me the date and time again.",
}

CONFIRM_DATE_PAST_SCHEDULE_ERROR: dict[LangCode, str] = {
    "pt-PT": "Não consegui agendar. Tenta de novo com a data e hora.",
    "pt-BR": "Não consegui agendar. Tente de novo com a data e hora.",
    "es": "No pude programarlo. Intenta de nuevo con fecha y hora.",
    "en": "I couldn't schedule it. Try again with the date and time.",
}

CONFIRM_EXPORT_CANCEL: dict[LangCode, str] = {
    "pt-PT": "❌ Exportação cancelada.",
    "pt-BR": "❌ Exportação cancelada.",
    "es": "❌ Exportación cancelada.",
    "en": "❌ Export cancelled.",
}

CONFIRM_EXPORT_EMPTY: dict[LangCode, str] = {
    "pt-PT": "📭 Nada para exportar.",
    "pt-BR": "📭 Nada para exportar.",
    "es": "📭 Nada para exportar.",
    "en": "📭 Nothing to export.",
}

CONFIRM_EXPORT_HEADER: dict[LangCode, str] = {
    "pt-PT": "📤 Exportação:",
    "pt-BR": "📤 Exportação:",
    "es": "📤 Exportación:",
    "en": "📤 Export:",
}

CONFIRM_EXPORT_ERROR: dict[LangCode, str] = {
    "pt-PT": "Erro ao exportar: {error}",
    "pt-BR": "Erro ao exportar: {error}",
    "es": "Error al exportar: {error}",
    "en": "Error exporting: {error}",
}

CONFIRM_EXPORT_ITEM_DONE: dict[LangCode, str] = {
    "pt-PT": " (feito)",
    "pt-BR": " (feito)",
    "es": " (hecho)",
    "en": " (done)",
}

CONFIRM_DELETE_CANCEL: dict[LangCode, str] = {
    "pt-PT": "✅ Cancelado. Nenhum dado foi apagado.",
    "pt-BR": "✅ Cancelado. Nenhum dado foi apagado.",
    "es": "✅ Cancelado. No se eliminó ningún dato.",
    "en": "✅ Cancelled. No data was deleted.",
}

CONFIRM_DELETE_DONE: dict[LangCode, str] = {
    "pt-PT": "🗑️ Todos os teus dados foram apagados.",
    "pt-BR": "🗑️ Todos os seus dados foram apagados.",
    "es": "🗑️ Todos tus datos han sido eliminados.",
    "en": "🗑️ All your data has been deleted.",
}

CONFIRM_DELETE_ERROR: dict[LangCode, str] = {
    "pt-PT": "Erro ao apagar: {error}",
    "pt-BR": "Erro ao apagar: {error}",
    "es": "Error al eliminar: {error}",
    "en": "Error deleting: {error}",
}

CONFIRM_COMPLETION_KEEP: dict[LangCode, str] = {
    "pt-PT": "Ok, o lembrete mantém-se. Reage com 👍 quando terminares.",
    "pt-BR": "Ok, o lembrete continua. Reaja com 👍 quando terminar.",
    "es": "Ok, el recordatorio se mantiene. Reacciona con 👍 cuando termines.",
    "en": "Ok, the reminder stays. React with 👍 when you're done.",
}

CONFIRM_COMPLETION_DONE: dict[LangCode, str] = {
    "pt-PT": "✅ Marcado como feito!",
    "pt-BR": "✅ Marcado como feito!",
    "es": "✅ ¡Marcado como hecho!",
    "en": "✅ Marked as done!",
}

CONFIRM_COMPLETION_ERROR: dict[LangCode, str] = {
    "pt-PT": "Ocorreu um erro. Tenta reagir com 👍 novamente ao lembrete.",
    "pt-BR": "Ocorreu um erro. Tente reagir com 👍 novamente ao lembrete.",
    "es": "Ocurrió un error. Intenta reaccionar con 👍 al recordatorio de nuevo.",
    "en": "An error occurred. Try reacting with 👍 to the reminder again.",
}

# ---------------------------------------------------------------------------
# settings_handlers.py response strings
# ---------------------------------------------------------------------------

SETTINGS_TZ_USAGE: dict[LangCode, str] = {
    "pt-PT": "🌍 Use: /tz Cidade (ex: /tz Lisboa) ou /tz Europe/Lisbon",
    "pt-BR": "🌍 Use: /tz Cidade (ex: /tz São Paulo) ou /tz America/Sao_Paulo",
    "es": "🌍 Usa: /tz Ciudad (ej: /tz Madrid) o /tz Europe/Madrid",
    "en": "🌍 Use: /tz City (e.g. /tz London) or /tz Europe/London",
}

SETTINGS_TZ_NOT_FOUND: dict[LangCode, str] = {
    "pt-PT": "🌍 Cidade \"{city}\" não reconhecida. Tenta: /tz Lisboa, /tz São Paulo ou /tz Europe/Lisbon (IANA).",
    "pt-BR": "🌍 Cidade \"{city}\" não reconhecida. Tente: /tz Lisboa, /tz São Paulo ou /tz America/Sao_Paulo (IANA).",
    "es": "🌍 Ciudad \"{city}\" no reconocida. Prueba: /tz Madrid, /tz Buenos Aires o /tz Europe/Madrid (IANA).",
    "en": "🌍 City \"{city}\" not recognised. Try: /tz London, /tz New York or /tz Europe/London (IANA).",
}

SETTINGS_TZ_SET: dict[LangCode, str] = {
    "pt-PT": "✅ Timezone definido: {tz}. As horas dos lembretes passam a ser mostradas no teu fuso.",
    "pt-BR": "✅ Timezone definido: {tz}. As horas dos lembretes passam a ser mostradas no seu fuso.",
    "es": "✅ Zona horaria definida: {tz}. Las horas de los recordatorios se mostrarán en tu zona horaria.",
    "en": "✅ Timezone set: {tz}. Reminder times will now be shown in your timezone.",
}

SETTINGS_TZ_INVALID: dict[LangCode, str] = {
    "pt-PT": "❌ Timezone inválido.",
    "pt-BR": "❌ Timezone inválido.",
    "es": "❌ Zona horaria inválida.",
    "en": "❌ Invalid timezone.",
}

SETTINGS_TZ_ERROR: dict[LangCode, str] = {
    "pt-PT": "Erro ao gravar timezone: {error}",
    "pt-BR": "Erro ao gravar timezone: {error}",
    "es": "Error al guardar zona horaria: {error}",
    "en": "Error saving timezone: {error}",
}

SETTINGS_LANG_USAGE: dict[LangCode, str] = {
    "pt-PT": "🌐 Idiomas disponíveis: /lang pt-pt | pt-br | es | en",
    "pt-BR": "🌐 Idiomas disponíveis: /lang pt-pt | pt-br | es | en",
    "es": "🌐 Idiomas disponibles: /lang pt-pt | pt-br | es | en",
    "en": "🌐 Available languages: /lang pt-pt | pt-br | es | en",
}

SETTINGS_LANG_SET: dict[LangCode, str] = {
    "pt-PT": "✅ Idioma definido: {lang}.",
    "pt-BR": "✅ Idioma definido: {lang}.",
    "es": "✅ Idioma definido: {lang}.",
    "en": "✅ Language set: {lang}.",
}

SETTINGS_LANG_ERROR: dict[LangCode, str] = {
    "pt-PT": "❌ Erro ao gravar idioma.",
    "pt-BR": "❌ Erro ao gravar idioma.",
    "es": "❌ Error al guardar el idioma.",
    "en": "❌ Error saving language.",
}

# ---------------------------------------------------------------------------
# hoje_semana.py inline strings
# ---------------------------------------------------------------------------

VIEW_NO_REMINDERS_TODAY: dict[LangCode, str] = {
    "pt-PT": "• Nenhum lembrete agendado para hoje.",
    "pt-BR": "• Nenhum lembrete agendado para hoje.",
    "es": "• Ningún recordatorio programado para hoy.",
    "en": "• No reminders scheduled for today.",
}


VIEW_NO_EVENTS_TODAY: dict[LangCode, str] = {
    "pt-PT": "• Nenhum evento hoje.",
    "pt-BR": "• Nenhum evento hoje.",
    "es": "• Ningún evento hoy.",
    "en": "• No events today.",
}

UNIFICADO_EMPTY: dict[LangCode, str] = {
    "pt-PT": "Não tens lembretes nem listas. Queres adicionar algum? 😊",
    "pt-BR": "Você não tem lembretes nem listas. Quer adicionar algum? 😊",
    "es": "No tienes recordatorios ni listas. ¿Quieres añadir algo? 😊",
    "en": "You don't have any reminders or lists. Would you like to add one? 😊",
}

VIEW_LABEL_HOJE: dict[LangCode, str] = {
    "pt-PT": "📅 **Hoje**",
    "pt-BR": "📅 **Hoje**",
    "es": "📅 **Hoy**",
    "en": "📅 **Today**",
}

