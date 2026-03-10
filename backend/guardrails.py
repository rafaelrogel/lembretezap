"""Guardrails sem custo de tokens: intervalo mínimo para recorrentes, filtro de pedidos absurdos
e evitação de loop infinito (não responder a mensagens triviais: ok, tá, não, emojis soltos).
"""

import re
import random

# Mensagens curtas/irrelevantes para as quais não respondemos (evita loop + custo de tokens).
# NÃO incluir "sim", "s", "yes", "1", "não", "no", "2": são usados em confirmações (ex.: lembrete)
# e precisam de ser processados pelo agente para executar a ação (criar lembrete, etc.).
TRIVIAL_REPLIES = frozenset({
    "ok", "ok.", "tá", "ta", "tá.", "ta.",
    "ah ok", "ah tá", "ah ta", "ah ok.", "ah tá.",
    "blz", "beleza", "tranquilo", "tranquilo.", "tudo bem", "tudo bom",
    "👍", "👌", "🙂", "😊", "👋", "✌", "🤝",
    "k", "k.", "kk", "kkk", "certo", "certinho",
    "valeu", "obrigado", "obrigada", "obg", "thx", "thanks",
    "ya", "yep", "yup", "nop", "nope",
})
# Máximo de caracteres para considerar "só emojis/símbolos" como trivial
MAX_LEN_EMOJI_ONLY = 4

# Intervalo mínimo para lembretes recorrentes diários (evitar spam: beber água a cada 30 min, etc.)
MIN_RECURRING_INTERVAL_SECONDS = 2 * 60 * 60  # 2 horas
MIN_EVERY_SECONDS = MIN_RECURRING_INTERVAL_SECONDS
# Se o cliente insistir/reclamar, permitir até 30 min (nunca menos — absurdo)
RELAXED_MIN_INTERVAL_SECONDS = 30 * 60

# Padrões para detectar intervalos irrazoáveis (recorrentes com menos de 2h)
RESPIRAR_A_CADA_MIN = re.compile(
    r"\brespirar\s+(?:a\s+)?cada\s+(\d{1,2})\s*min",
    re.I,
)
# "beber agua a cada N min", "drink water every N min", etc.
AGUA_A_CADA = re.compile(
    r"\b(?:beber\s+)?(?:água|agua|water)\s+(?:a\s+)?cada\s+(\d{1,3})\s*min",
    re.I,
)
WATER_EVERY_MIN = re.compile(
    r"\b(?:drink\s+)?water\s+every\s+(\d{1,3})\s*min",
    re.I,
)
A_CADA_MIN_GENERIC = re.compile(
    r"\ba\s+cada\s+(\d{1,3})\s*min",
    re.I,
)
EVERY_MIN_GENERIC = re.compile(
    r"\bevery\s+(\d{1,3})\s*min",
    re.I,
)
# "a cada 1 hora", "every 1 hour" — intervalo < 2h
A_CADA_HORA = re.compile(
    r"\ba\s+cada\s+1\s*hora",
    re.I,
)
EVERY_ONE_HOUR = re.compile(
    r"\bevery\s+1\s*hour",
    re.I,
)

# Indicadores de que o assistente rejeitou por intervalo curto (para detectar insistência)
_INTERVAL_REJECTION_MARKERS = ("2 horas", "2h", "mínimo", "intervalo", "minimo")

# Palavras que sugerem insistência/reclamação do cliente
_INSISTENCE_KEYWORDS = (
    "insisto", "preciso", "necessito", "por favor", "preciso mesmo", "mesmo assim",
    "médicos", "medicos", "médico", "receita", "recomendou", "recomendaram",
    "doctor", "doctors", "prescribed", "medical", "insist", "need", "please",
    "aceita", "aceite", "accept", "faz assim", "assim mesmo", "desta vez",
)

# Mensagens vagas que NÃO descrevem o conteúdo do lembrete (tipo, não evento)
_VAGUE_REMINDER_PATTERNS = (
    r"^(lembrete|alerta|aviso|lembra[- ]?me|lembra[- ]?mi|reminder|alarm)\s*$",
    r"^(lembrete|alerta|aviso|reminder)\s+(?:para\s+)?(?:amanhã|hoje|às?\s*\d|as\s*\d)",  # "lembrete amanhã" sem evento
    r"^(?:só\s+)?(?:um\s+)?(?:lembrete|alerta)\s*$",
)
_VAGUE_REMINDER_RE = re.compile("|".join(_VAGUE_REMINDER_PATTERNS), re.I)


# Palavras de tempo (remover para ver se sobra conteúdo real)
_TIME_WORDS = {
    "lembrete", "alerta", "aviso", "reminder", "alarm", "lembra", "lembra-me",
    "amanhã", "amanha", "hoje", "depois", "às", "as", "à", "a", "as", "hr",
    "hora", "horas", "min", "minutos", "segunda", "terça", "quarta", "quinta",
    "sexta", "sábado", "sabado", "domingo", "dia", "semana", "mês", "mes",
    "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out",
    "nov", "dez", "em", "de", "para", "por", "favor", "pf", "obrigado",
    "daqui", "dentro", "vão", "ser", "pode", "será", "seria", "vou",
    "tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "at", "for", "am", "pm", "in", "within",
}


def is_vague_reminder_message(message: str | None) -> bool:
    """
    True se a mensagem não descreve O QUE lembrar (ex.: "lembrete", "alerta", "lembrete amanhã 10h").
    Nestes casos, perguntar "De que é o lembrete?" antes de criar.
    """
    if not message or not message.strip():
        return True
    t = message.strip().lower()
    if len(t) < 3:
        return True
    # Palavras da mensagem (incl. números como tokens)
    words = set(re.findall(r"\b\w+\b", t))
    # Remover tempo + tipo → ver se sobra conteúdo concreto
    content_words = words - _TIME_WORDS
    # Remover tokens que são só dígitos ou hora (10h, 9h, etc.)
    content_words = {
        w for w in content_words
        if not w.isdigit() and not (len(w) <= 4 and w[:-1].isdigit() and w[-1] in "hH")
    }
    # Se sobrou pouco ou nada concreto → vago
    if len(content_words) == 0:
        return True
    # "lembrete X" onde X é só tempo → vago (ex.: lembrete segunda 10h)
    if len(content_words) <= 1 and any(w in t for w in ("lembrete", "alerta", "aviso", "reminder")):
        return True
    return False


# Padrões que indicam pedido absurdo/impossível (viagem no tempo, etc.)
ABSURD_PATTERNS = re.compile(
    r"\b(viagem\s+no\s+tempo|viajar\s+no\s+tempo|time\s+travel|"
    r"teletransporte|teletransportar|marty\s+mcfly|delorean|"
    r"máquina\s+do\s+tempo|maquina\s+do\s+tempo)\b",
    re.I,
)

# Respostas para intervalos irrazoáveis (< 2h entre repetições)
FUN_RESPONSES_INTERVAL_SHORT = [
    "O intervalo mínimo para lembretes recorrentes é 2 horas — senão vira spam. 😊 Ex.: a cada 2 horas ou todo dia às 8h e às 14h.",
    "Para evitar bombardeamento de notificações, o mínimo entre repetições é 2 horas. Ex.: a cada 3 horas ou 3 vezes ao dia.",
]

# Respostas divertidas para viagem no tempo / impossíveis (uma escolhida ao acaso)
FUN_RESPONSES_ABSURD = [
    "Não sou o Marty McFly nem o professor do DeLorean — viagem no tempo fica para outra vida. 😄",
    "Viagem no tempo? Ainda não temos o capacitor de fluxo. Quando tiver, aviso! ⏰",
    "Isso é nível De Volta para o Futuro. Por aqui só lembretes no tempo presente. 😅",
    "Pedido muito à frente no tempo (e no espaço). Vamos manter os pés no presente? 🚀",
    "Adorava, mas a máquina do tempo ainda está na garantia. Tenta um lembrete no tempo real! 😄",
]


def is_complex_request(text: str) -> bool:
    """
    True se a mensagem parece ser um "wall of text" ou conter múltiplos pedidos distintos
    (ex.: "marca agenda, adiciona pão à lista e cria lembrete").
    Neste caso, os handlers regex (NLU local) devem ignorar e deixar a mensagem
    fluir para o LLM agent, que consegue decompor as múltiplas intenções.
    """
    if not text or len(text.strip()) < 40:
        return False
        
    t = text.strip().lower()
    
    # Indicadores gramaticais de múltiplos pedidos
    has_multiple_actions = sum(1 for kw in [" e ", " também ", " além disso ", " ah ", " já agora ", " adicione ", " adiciona ", " cria ", " crie ", " lembra ", " lembre "] if kw in t)
    
    # Se tiver texto razoavelmente longo (> 80 chars) E múltiplas conjunções/verbos de acção
    if len(t) > 80 and has_multiple_actions >= 2:
        return True
        
    # Combinações de palavras-chave de diferentes domínios (agenda + lista + lembrete)
    has_list_intent = any(kw in t for kw in [" lista ", " compras ", " mercado "])
    has_event_intent = any(kw in t for kw in [" agenda ", " churrasco ", " consulta ", " reunião "])
    has_reminder_intent = any(kw in t for kw in [" lembrete ", " lembra ", " avisar ", " avisa "])
    has_pomodoro_intent = any(kw in t for kw in [" pomodoro ", " foco "])
    
    intents_count = sum([has_list_intent, has_event_intent, has_reminder_intent, has_pomodoro_intent])
    
    return intents_count >= 2



def is_absurd_request(text: str, allow_relaxed: bool = False) -> str | None:
    """
    Detecta pedidos absurdos: viagem no tempo, intervalos curtos em recorrentes.
    allow_relaxed: se True (cliente insistiu/reclamou), permite até 30 min. Nunca < 30 min.
    Retorna None se OK, ou mensagem para enviar ao utilizador se for absurdo.
    """
    if not text or not text.strip():
        return None
    t = text.strip()
    min_minutes = 30 if allow_relaxed else 120  # 30 min razoável quando insiste; 2h normal
    for pattern in (RESPIRAR_A_CADA_MIN, AGUA_A_CADA, WATER_EVERY_MIN, A_CADA_MIN_GENERIC, EVERY_MIN_GENERIC):
        m = pattern.search(t)
        if m:
            try:
                n = int(m.group(1))
                if 0 < n < min_minutes:
                    return random.choice(FUN_RESPONSES_INTERVAL_SHORT)
            except ValueError:
                pass
    if not allow_relaxed:
        for pattern in (A_CADA_HORA, EVERY_ONE_HOUR):
            if pattern.search(t):
                return random.choice(FUN_RESPONSES_INTERVAL_SHORT)
    if ABSURD_PATTERNS.search(t):
        return random.choice(FUN_RESPONSES_ABSURD)
    return None


def cron_min_interval_seconds(expr: str) -> int | None:
    """
    Retorna o intervalo mínimo em segundos entre execuções de uma expressão cron.
    Usa croniter para obter as próximas 5 execuções e calcula o menor gap.
    Retorna None se não conseguir analisar.
    """
    if not expr or not expr.strip():
        return None
    try:
        from croniter import croniter
        import time
        c = croniter(expr.strip(), time.time())
        times = [c.get_next() for _ in range(6)]
        if len(times) < 2:
            return None
        gaps = [int(times[i + 1] - times[i]) for i in range(len(times) - 1)]
        return min(gaps) if gaps else None
    except Exception:
        return None


def is_cron_interval_too_short(expr: str, allow_relaxed: bool = False) -> bool:
    """True se o cron dispara com intervalo < mínimo entre execuções."""
    if not expr or not expr.strip():
        return False
    min_interval = RELAXED_MIN_INTERVAL_SECONDS if allow_relaxed else MIN_RECURRING_INTERVAL_SECONDS
    min_minutes = min_interval // 60
    parts = expr.strip().split()
    if len(parts) < 2:
        return False
    min_field, hour_field = parts[0], parts[1]
    if min_field.startswith("*/"):
        try:
            n = int(min_field[2:].split(",")[0])
            if 0 < n < min_minutes:
                return True
        except ValueError:
            pass
    if not allow_relaxed and hour_field.strip() == "*":
        return True
    if allow_relaxed and hour_field.strip() == "*":
        return False  # 1h OK quando relaxed
    min_sec = cron_min_interval_seconds(expr)
    return min_sec is not None and 0 < min_sec < min_interval


async def user_insisting_on_interval_rejection(
    session_manager,
    channel: str,
    chat_id: str,
    current_content: str,
    scope_provider=None,
    scope_model: str = "",
) -> bool:
    """
    True se o assistente rejeitou por intervalo curto e o utilizador está a insistir/reclamar.
    Quando True, permitir intervalo relaxado (30 min) se o pedido for razoável.
    """
    if not session_manager or not current_content or len(current_content.strip()) < 3:
        return False
    try:
        key = f"{channel}:{chat_id}"
        session = session_manager.get_or_create(key)
        recent = (session.messages or [])[-6:]
        if len(recent) < 2:
            return False
        last_assistant = None
        for m in reversed(recent):
            if m.get("role") == "assistant":
                last_assistant = (m.get("content") or "").strip()
                break
        if not last_assistant or not any(m in last_assistant.lower() for m in _INTERVAL_REJECTION_MARKERS):
            return False
        tl = current_content.strip().lower()
        if any(kw in tl for kw in _INSISTENCE_KEYWORDS):
            return True
        if scope_provider and scope_model:
            conv_text = "\n".join(
                f"{m.get('role','?')}: {(m.get('content') or '')[:150]}"
                for m in recent
            ) + f"\nuser: {current_content[:200]}"
            prompt = f"""O assistente rejeitou um lembrete por "intervalo mínimo 2 horas".
O utilizador respondeu: "{current_content[:200]}"
O utilizador está a INSISTIR ou RECLAMAR, pedindo exceção? (ex.: precisa mesmo, médicos recomendaram, por favor)
Responde APENAS: SIM ou NAO"""
            try:
                r = await scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=scope_model,
                    max_tokens=10,
                    temperature=0,
                )
                raw = (r.content or "").strip().upper()
                return "SIM" in raw or raw.startswith("S")
            except Exception:
                pass
    except Exception:
        pass
    return False


def should_skip_reply(content: str) -> bool:
    """
    True se a mensagem é trivial e não devemos responder (evita loop e custo de tokens).
    Ex.: "ok", "tá", "não", "sim", emojis soltos (👍, 😊). Zero tokens — só regex e set.
    """
    if not content:
        return True
    t = content.strip()
    if not t:
        return True
    # Normalizado para comparação: minúsculas, sem pontuação final
    normalized = t.lower().rstrip(".!?¿¡").strip()
    if normalized in TRIVIAL_REPLIES:
        return True
    # Mensagem muito curta e sem letras/números (só emojis ou símbolos)
    if len(t) <= MAX_LEN_EMOJI_ONLY and not any(c.isalnum() for c in t):
        return True
    return False
