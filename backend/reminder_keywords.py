"""Repositorio de keywords e frases para deteção de lembretes.
Suporta PT-PT, PT-BR, ES, EN.
"""

# Português (Brasil e Portugal)
PT_KEYWORDS = [
    "lembrar", "lembra", "lembre", "lembrete", "lembrança", "lembra-me", "lembre-me", "me lembre", "me lembra",
    "avisar", "avisa", "avise", "aviso", "avisa-me", "avise-me", "me avisa", "me avise",
    "recordar", "recorda", "recorde", "recordar-me", "recorde-me", "me recorda", "me recorde",
    "anotar", "anota", "anote", "anota aí", "anota ai", "anote aí", "faz uma nota", "cria uma nota",
    "agendar", "agenda", "agende", "agendamento",
    "não me deixe esquecer", "não esqueças", "não esquece", "nao me deixe esquecer", "nao esquecas", "nao esquece",
    "não te esqueças", "nao te esquecas", "não se esqueça", "nao se esqueca",
    "me dá um toque", "me da um toque", "dá-me um toque", "da-me um toque",
    "quero ser lembrado", "quero que me lembres", "quero que você me lembre", "quero um lembrete",
    "me desperta", "desperta-me", "despertar", "alerta", "alertar", "me alerta", "cria um alerta",
    "marca aí", "marcar", "marca", "marcar compromisso",
    "põe um lembrete", "poe um lembrete", "coloca um lembrete", "colocar lembrete",
    "não deixa eu esquecer", "nao deixa eu esquecer", "não me deixes esquecer", "nao me deixes esquecer",
    "aponta aí", "aponta", "apontar", "regista", "registar", "registre", "registrar",
    "me sinaliza", "sinalizar", "podes me lembrar", "pode me lembrar", "consegue me lembrar",
    "lembrar de", "lembra de", "lembre de", "avisa de", "avise de",
    "lembre-me disso", "lembra-me disso", "me lembre disso",
    "preciso de um lembrete", "tenho que lembrar", "tenho de lembrar",
    "lembrador", "me avisa quando", "me avise quando", "avisa-me quando"
]

# Español
ES_KEYWORDS = [
    "recordar", "recuerda", "recuerde", "recordatorio", "recuérdame", "recuerdame", "me recuerda", "me recuerde",
    "avisar", "avisa", "avise", "aviso", "avísame", "avisame", "me avisa", "me avise",
    "notificar", "notifica", "notifique", "notifícame", "notificame",
    "agendar", "agenda", "agende", "cita", "hacer una cita",
    "no me dejes olvidar", "no te olvides", "no se olvide", "que no se me olvide",
    "apuntar", "apunta", "apunte", "haz una nota", "crear una nota",
    "quiero que me recuerdes", "quiero ser recordado", "necesito un recordatorio",
    "ponme un recordatorio", "pon un recordatorio", "crear recordatorio",
    "dame un toque", "avísame cuando", "avisame cuando",
    "despertar", "despiértame", "alerta", "alertar", "pon una alerta",
    "anotar", "anota", "anote", "hazme acuerdo", "hazme el favor de recordar",
    "no olvides avisarme", "no olvide avisarme",
    "podrías recordarme", "puede recordarme", "puedes recordarme",
    "marcar", "marca", "registro", "registrar", "regístrame",
    "señalizar", "dame una señal", "avísame a las"
]

# English
EN_KEYWORDS = [
    "remind", "reminds", "reminder", "remind me", "remind me to", "be reminded",
    "notify", "notifies", "notification", "notify me",
    "don't let me forget", "dont let me forget", "make sure i remember", "do not forget",
    "set a reminder", "make a reminder", "create a reminder", "schedule a reminder",
    "i want to be reminded", "i need a reminder", "give me a reminder",
    "alert", "alert me", "set an alert", "create an alert",
    "take a note", "note down", "note this", "jot down",
    "mark it", "mark down", "put it on the agenda", "agenda",
    "keep me posted", "let me know", "ping me", "give me a ping",
    "don't forget to tell me", "dont forget to tell me",
    "could you remind me", " can you remind me", "please remind me",
    "would you remind me", "mind me", "keep me in mind",
    "wake me up", "alarm", "set an alarm", "alarm me",
    "put a reminder", "place a reminder", "add a reminder",
    "inform me", "keep me informed", "signal me",
    "remind me about", "remind me later"
]

# Lista unificada para deteção simples
ALL_REMINDER_KEYWORDS = sorted(list(set(PT_KEYWORDS + ES_KEYWORDS + EN_KEYWORDS)), key=len, reverse=True)
