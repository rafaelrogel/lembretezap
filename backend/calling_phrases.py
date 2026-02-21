"""
Frases de "chamada" ao bot: mensagens curtas que só puxam atenção (rapaz?, robô?, tá aí?, tá ligado?, etc.).
Usado para responder com uma frase rápida (Xiaomi) em vez de acionar o LLM principal.
Centenas de expressões por idioma (pt-PT, pt-BR, es, en), expandidas com variantes (?, !, sem acento).
"""

from typing import Literal

LangCode = Literal["pt-PT", "pt-BR", "es", "en"]

# --- Base: vocativos e frases "estás aí?" por idioma ---

_BASE_PT_BR = [
    "organizador", "organizadora", "assistente", "robô", "robot", "robo", "bot", "secretária", "secretario",
    "cara", "rapaz", "mano", "maninho", "amigo", "amiga", "chefe", "parceiro", "parceira", "migo", "miga",
    "fera", "véi", "velho", "minha filha", "meu filho", "brother", "brah", "gente", "pessoal",
    "cadê você", "cadê tu", "onde você", "onde tu", "tá aí", "está aí", "ta ai", "esta ai",
    "tá ligado", "ta ligado", "tá conectado", "ta conectado", "você está aí", "você ta aí",
    "está conectado", "tá online", "ta online", "está online", "sumiu", "responde", "me atende",
    "pode me atender", "alô", "alô alô", "oi bot", "oi robô", "oi organizador", "olá organizador",
    "e aí organizador", "e aí bot", "e aí robô", "fala organizador", "fala bot", "fala robô",
    "opa organizador", "opa bot", "hey assistente", "ei assistente", "oi assistente", "olá assistente",
    "tá aí sim", "tá aí?", "está aí?", "tá ligado?", "tá conectado?", "cadê?", "onde cê",
    "tô aqui", "to aqui", "você tá aí", "ce ta ai", "tá aí ou não", "responde aí", "atende aí",
    "me responde", "me atende aí", "alguém aí", "tem alguém aí", "alô bot", "alô robô",
    "chamando", "te chamei", "te chamo", "oi cara", "oi rapaz", "oi mano", "olá cara", "e aí cara",
    "e aí rapaz", "e aí mano", "fala cara", "fala rapaz", "fala mano", "opa cara", "opa rapaz",
    "hey cara", "hey rapaz", "ei cara", "ei rapaz", "oi chefe", "olá chefe", "e aí chefe",
    "fala chefe", "opa chefe", "oi amigo", "olá amigo", "e aí amigo", "fala amigo", "opa amigo",
    "oi secretária", "olá secretária", "e aí secretária", "oi assistente", "olá assistente",
    "estou aqui", "tô aí", "to aí", "você está", "ce está", "você ta", "ce ta",
    "tá aí organizador", "está aí organizador", "tá aí bot", "tá aí robô", "tá aí assistente",
    "disponível", "está disponível", "ta disponivel", "pode vir", "tô te chamando",
    "te esperando", "tô esperando", "cadê o bot", "cadê o robô", "cadê a assistente",
    "onde o bot", "onde o robô", "onde a assistente", "bot cadê", "robô cadê",
    "organizador cadê", "assistente cadê", "oi migo", "olá migo", "e aí migo", "fala migo",
    "oi véi", "e aí véi", "fala véi", "opa véi", "oi velho", "e aí velho", "fala velho",
    "oi fera", "e aí fera", "fala fera", "opa fera", "oi brother", "e aí brother", "fala brother",
    "oi parceiro", "e aí parceiro", "fala parceiro", "opa parceiro", "oi gente", "e aí gente",
    "fala gente", "opa gente", "oi pessoal", "e aí pessoal", "fala pessoal", "olá pessoal",
    "tá ligado cara", "tá ligado rapaz", "tá ligado mano", "tá conectado aí", "conectado",
    "online aí", "responde aí cara", "responde aí rapaz", "me atende aí", "atende aqui",
    "alô alguém", "tem alguém", "alguém me atende", "por favor atende", "atende por favor",
    "tô chamando", "to chamando", "chamei você", "te chamei aí", "oi robo", "ola robo",
    "oi robot", "ola robot", "e aí robot", "fala robot", "opa robot", "hey bot", "hey robo",
    "ei bot", "ei robo", "ei robot", "hello bot", "hello robo", "hi bot", "hi robo",
    "hello organizador", "hi organizador", "hey organizador", "hello assistente", "hi assistente",
]

_BASE_PT_PT = [
    "organizador", "organizadora", "assistente", "robô", "robot", "robo", "bot", "secretária", "secretário",
    "rapaz", "cara", "amigo", "amiga", "chefe", "pessoal", "miúdo", "miúda", "moço", "moça",
    "cadê tu", "onde estás", "onde tu", "estás aí", "tás aí", "tas ai", "estás aí",
    "estás ligado", "estás conectado", "estás online", "estás disponível", "sumiste",
    "responde", "atende", "atende-me", "podes atender", "estou a chamar", "estou a chamar-te",
    "alô", "alô alô", "oi organizador", "olá organizador", "ei organizador", "e então organizador",
    "fala organizador", "fala bot", "fala robô", "opa organizador", "opa bot", "opa robô",
    "oi bot", "oi robô", "olá bot", "olá robô", "e então bot", "e então robô", "e então assistente",
    "oi assistente", "olá assistente", "fala assistente", "opa assistente", "hey assistente", "ei assistente",
    "estás aí?", "tás aí?", "estás ligado?", "estás conectado?", "cadê?", "onde é que estás",
    "estou aqui", "estou cá", "tu estás aí", "estás aí ou não", "responde lá", "atende lá",
    "alguém aí", "há alguém aí", "alô bot", "alô robô", "chamei-te", "chamo-te", "estou a chamar",
    "oi rapaz", "oi cara", "olá rapaz", "olá cara", "e então rapaz", "e então cara", "fala rapaz",
    "fala cara", "opa rapaz", "opa cara", "oi amigo", "olá amigo", "e então amigo", "fala amigo",
    "opa amigo", "oi chefe", "olá chefe", "e então chefe", "fala chefe", "opa chefe",
    "oi secretária", "olá secretária", "e então secretária", "estou aqui", "tu estás",
    "estás disponível", "estás livre", "podes vir", "estou a te chamar", "estou à tua espera",
    "cadê o bot", "cadê o robô", "cadê a assistente", "onde está o bot", "onde está o robô",
    "bot cadê", "robô cadê", "organizador cadê", "assistente cadê", "oi moço", "olá moço",
    "e então moço", "fala moço", "oi moça", "olá moça", "e então moça", "fala moça",
    "oi miúdo", "olá miúdo", "e então miúdo", "oi pessoal", "olá pessoal", "e então pessoal",
    "estás ligado rapaz", "estás conectado aí", "conectado", "online aí", "responde lá rapaz",
    "atende-me lá", "atende aqui", "há alguém", "alguém me atende", "por favor atende",
    "estou a chamar-te", "chamei-te aí", "oi robo", "olá robo", "oi robot", "olá robot",
    "e então robot", "fala robot", "opa robot", "hey bot", "hey robo", "ei bot", "ei robo",
    "hello bot", "hello robo", "hi bot", "hi robo", "hello organizador", "hi organizador",
    "hey organizador", "hello assistente", "hi assistente", "hey assistente",
]

_BASE_ES = [
    "organizador", "organizadora", "asistente", "asistenta", "robot", "robôt", "robo", "bot", "secretario", "secretaria",
    "tío", "tía", "amigo", "amiga", "jefe", "chefe", "chico", "chica", "chaval", "tío",
    "estás ahí", "estas ahi", "estás ahí", "¿estás ahí", "estás ahí?", "estas ahi?",
    "dónde estás", "donde estas", "dónde te has metido", "dónde andas", "donde andas",
    "estás conectado", "estas conectado", "estás en línea", "estas en linea", "estás disponible",
    "contestas", "contesta", "respóndeme", "respondeme", "atiéndeme", "atiendeme", "por favor atiende",
    "hola", "hola bot", "hola robot", "hola organizador", "hola asistente", "hola secretario",
    "oye", "oye bot", "oye robot", "oye organizador", "oye asistente", "ey bot", "ey robot",
    "eh bot", "eh robot", "eh organizador", "eh asistente", "buenas", "buenas bot", "buenas robot",
    "estás ahí?", "estás conectado?", "estás en línea?", "¿dónde estás?", "donde estas?",
    "estoy aquí", "estoy aqui", "tú estás ahí", "tu estas ahi", "estás ahí o no", "contesta ya",
    "atiende ya", "hay alguien", "alguien ahí", "aló", "aló aló", "te llamo", "te estoy llamando",
    "hola chico", "hola chica", "hola amigo", "hola amiga", "oye chico", "oye amigo", "ey amigo",
    "hola jefe", "oye jefe", "hola tío", "oye tío", "ey tío", "buenas tío", "hola chaval",
    "estoy aquí", "tú estás", "tu estas", "estás disponible", "estás libre", "puedes venir",
    "te estoy llamando", "te espero", "dónde está el bot", "dónde está el robot", "donde esta el bot",
    "bot dónde", "robot dónde", "organizador dónde", "asistente dónde", "hola robo", "hola robot",
    "oye robo", "oye robot", "estás conectado tío", "estás en línea ahí", "en línea", "conectado ahí",
    "contesta ya tío", "atiéndeme ya", "atiendeme ya", "atiende aquí", "hay alguien ahí",
    "alguien me atiende", "por favor contesta", "estoy llamando", "te llamé", "hola robo",
    "buenas robo", "ey robo", "eh robo", "hello bot", "hello robot", "hi bot", "hi robot",
    "hello organizador", "hi organizador", "hello asistente", "hi asistente", "hey bot",
    "hey robot", "hey organizador", "hey asistente", "responde", "respóndeme por favor",
    "tá aí", "ta ai", "cadê você", "onde você", "oi bot", "olá bot", "e aí bot",
]

_BASE_EN = [
    "organizer", "assistant", "robot", "bot", "secretary", "buddy", "dude", "mate", "man", "friend",
    "chief", "boss", "hey", "hey bot", "hey robot", "hey assistant", "hey organizer",
    "are you there", "you there", "you there?", "are you there?", "where are you", "where are you?",
    "are you online", "are you connected", "you online", "you connected", "you there",
    "reply", "respond", "answer me", "answer", "attend", "please respond", "please answer",
    "hello", "hello bot", "hello robot", "hello assistant", "hello organizer", "hi bot", "hi robot",
    "hi assistant", "hi organizer", "hey dude", "hey man", "hey buddy", "hey mate", "hey friend",
    "hey chief", "hey boss", "hello dude", "hello man", "hi dude", "hi man", "yo bot", "yo robot",
    "yo assistant", "yo organizer", "yo dude", "yo man", "sup bot", "sup robot", "what's up bot",
    "i'm here", "i am here", "you there?", "you online?", "you connected?", "anybody there",
    "anyone there", "someone there", "hello anyone", "calling you", "calling", "calling bot",
    "calling robot", "call you", "called you", "waiting for you", "waiting", "are you available",
    "you available", "you free", "can you come", "hello dude", "hi dude", "hey there bot",
    "hey there robot", "hey there assistant", "where is the bot", "where is the robot",
    "where's the bot", "where's the robot", "bot where", "robot where", "assistant where",
    "organizer where", "hello robo", "hi robo", "hey robo", "are you connected dude",
    "you online there", "online there", "connected there", "reply dude", "answer me there",
    "attend here", "anybody there", "someone attend", "please attend", "i'm calling",
    "i called you", "hello robot", "hi robot", "yo robo", "sup robo", "hello assistant",
    "hi assistant", "hey assistant", "oi bot", "ola bot", "hola bot", "tá aí", "ta ai",
    "cadê você", "estás ahí", "organizador", "asistente", "rapaz", "cara", "tío",
]

# --- Expansão: variantes com pontuação e combinações para chegar a ~500 por idioma ---

def _expand_phrases(base: list[str], greetings: list[str], target_size: int = 500) -> set[str]:
    """Expande base + greetings com variantes (?, !, sem acento) até ~target_size."""
    out: set[str] = set()
    for p in base:
        out.add(p.strip().lower())
        out.add((p.strip().lower() + "?"))
        out.add((p.strip().lower() + "!"))
        # sem acentos (aproximado)
        for c, r in [("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"), ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"), ("ú", "u"), ("ç", "c"), ("ñ", "n")]:
            if c in p:
                q = p.replace(c, r).strip().lower()
                out.add(q)
                out.add(q + "?")
                out.add(q + "!")

    # Combinações greeting + termo (ex.: "oi" + "organizador" -> "oi organizador" já está na base; adicionar "oi " + cada vocativo)
    vocatives: list[str] = []
    for p in base:
        if len(p.split()) <= 2 and p not in greetings:
            vocatives.append(p.strip().lower())
    for g in greetings:
        for v in vocatives[:40]:  # limitar para não explodir
            out.add(f"{g} {v}")
            out.add(f"{g} {v}?")
            out.add(f"{g} {v}!")

    # Repetir primeiros termos com " " no início/fim para variantes
    extra = list(out)[:100]
    for e in extra:
        if "?" not in e and "!" not in e:
            out.add(e + " ?")
            out.add(e + " !")

    # Se ainda faltar, duplicar base com pequenas variações
    while len(out) < target_size and base:
        for p in base[:50]:
            out.add(p.strip().lower())
            out.add((p.strip().lower()).replace("  ", " "))
        break

    return out


def _all_phrases() -> set[str]:
    """Conjunto único de todas as frases de chamada (todos os idiomas)."""
    greetings_pt_br = ["oi", "olá", "ola", "e aí", "e ai", "hey", "ei", "opa", "fala", "falou"]
    greetings_pt_pt = ["oi", "olá", "ola", "e então", "e entao", "hey", "ei", "opa", "fala"]
    greetings_es = ["hola", "oye", "ey", "eh", "buenas", "qué tal", "que tal"]
    greetings_en = ["hello", "hi", "hey", "yo", "sup", "hey there"]

    s: set[str] = set()
    s |= _expand_phrases(_BASE_PT_BR, greetings_pt_br)
    s |= _expand_phrases(_BASE_PT_PT, greetings_pt_pt)
    s |= _expand_phrases(_BASE_ES, greetings_es)
    s |= _expand_phrases(_BASE_EN, greetings_en)
    return s


# Cache do conjunto (carregado uma vez)
_CALLING_PHRASES: set[str] | None = None


def get_calling_phrases() -> set[str]:
    """Retorna o conjunto de frases de chamada (todas as línguas)."""
    global _CALLING_PHRASES
    if _CALLING_PHRASES is None:
        _CALLING_PHRASES = _all_phrases()
    return _CALLING_PHRASES


# Palavras que indicam pedido concreto — não tratar como "chamada"; encaminhar ao LLM
_TASK_KEYWORDS = frozenset([
    "lembrete", "lembretes", "recordatorio", "recordatorios", "reminder", "reminders",
    "lembrar", "lembra", "lembre", "recordar", "recorda", "recorde", "avisar", "avisa", "avise",
    "próximo", "proximo", "próximos", "next", "agenda", "evento", "eventos", "event",
    "lista", "listas", "list", "hoje", "amanhã", "amanha", "tomorrow", "today",
    "horário", "horario", "schedule", "que horas", "qual é o", "qual e o", "what is my",
    "qual é o meu", "qual e o meu", "meu nome", "my name", "mi nombre",
    "quero", "preciso", "preciso de", "need", "want", "adiciona", "add", "remover",
    "criar", "criar um", "create", "marcar", "agendar", "schedule",
    "ajuda", "help", "comandos", "stats", "estatísticas", "estatisticas",
])


def is_calling_message(content: str | None, max_length: int = 42) -> bool:
    """
    True se a mensagem for uma "chamada" curta ao bot (rapaz?, robô?, tá aí?, etc.),
    sem pedido concreto. Não considera mensagens que começam com /.
    Mensagens com ? e palavras de tarefa (lembrete, próximo, agenda, etc.) não são chamada.
    """
    if not content or not content.strip():
        return False
    text = content.strip()
    if len(text) > max_length:
        return False
    if text.startswith("/"):
        return False
    lower = text.lower()
    # Se contém palavras de pedido concreto (lembrete, nome, agenda, etc.), não é "chamada" — encaminhar ao LLM
    if any(kw in lower for kw in _TASK_KEYWORDS):
        return False
    phrases = get_calling_phrases()
    return any(p in lower for p in phrases)


def count_phrases_per_lang() -> dict[str, int]:
    """Contagem de frases por idioma (para verificação)."""
    greetings_pt_br = ["oi", "olá", "ola", "e aí", "e ai", "hey", "ei", "opa", "fala", "falou"]
    greetings_pt_pt = ["oi", "olá", "ola", "e então", "e entao", "hey", "ei", "opa", "fala"]
    greetings_es = ["hola", "oye", "ey", "eh", "buenas", "qué tal", "que tal"]
    greetings_en = ["hello", "hi", "hey", "yo", "sup", "hey there"]
    return {
        "pt-BR": len(_expand_phrases(_BASE_PT_BR, greetings_pt_br)),
        "pt-PT": len(_expand_phrases(_BASE_PT_PT, greetings_pt_pt)),
        "es": len(_expand_phrases(_BASE_ES, greetings_es)),
        "en": len(_expand_phrases(_BASE_EN, greetings_en)),
    }
