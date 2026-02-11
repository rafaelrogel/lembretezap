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

# Intervalo mínimo para lembretes recorrentes (ex.: "a cada 10 min" → rejeitar)
MIN_EVERY_SECONDS = 30 * 60  # 30 minutos

# Padrão "respirar a cada N min" (N capturado para checar se < 30)
RESPIRAR_A_CADA_MIN = re.compile(
    r"\brespirar\s+(?:a\s+)?cada\s+(\d{1,2})\s*min",
    re.I,
)

# Padrões que indicam pedido absurdo/impossível (viagem no tempo, etc.)
ABSURD_PATTERNS = re.compile(
    r"\b(viagem\s+no\s+tempo|viajar\s+no\s+tempo|time\s+travel|"
    r"teletransporte|teletransportar|marty\s+mcfly|delorean|"
    r"máquina\s+do\s+tempo|maquina\s+do\s+tempo)\b",
    re.I,
)

# Respostas para "respirar a cada X min" (intervalo curto)
FUN_RESPONSES_RESPIRAR = [
    "Respirar a cada poucos minutos? O corpo já cuida disso sozinho. 😄 Lembretes recorrentes aqui são a cada 30 min no mínimo.",
    "Até adorava lembrar-te de respirar, mas o mínimo é a cada 30 minutos — senão vira spam. 🌬️",
]

# Respostas divertidas para viagem no tempo / impossíveis (uma escolhida ao acaso)
FUN_RESPONSES_ABSURD = [
    "Não sou o Marty McFly nem o professor do DeLorean — viagem no tempo fica para outra vida. 😄",
    "Viagem no tempo? Ainda não temos o capacitor de fluxo. Quando tiver, aviso! ⏰",
    "Isso é nível De Volta para o Futuro. Por aqui só lembretes no tempo presente. 😅",
    "Pedido muito à frente no tempo (e no espaço). Vamos manter os pés no presente? 🚀",
    "Adorava, mas a máquina do tempo ainda está na garantia. Tenta um lembrete no tempo real! 😄",
]


def is_absurd_request(text: str) -> str | None:
    """
    Detecta pedidos absurdos (viagem no tempo, teletransporte, respirar a cada poucos min, etc.).
    Retorna None se OK, ou uma mensagem divertida para enviar ao utilizador se for absurdo.
    Zero tokens — só regex e lista fixa.
    """
    if not text or not text.strip():
        return None
    t = text.strip()
    # "respirar a cada N min" com N < 30 → resposta específica
    m = RESPIRAR_A_CADA_MIN.search(t)
    if m:
        try:
            n = int(m.group(1))
            if n < 30:
                return random.choice(FUN_RESPONSES_RESPIRAR)
        except ValueError:
            pass
    if ABSURD_PATTERNS.search(t):
        return random.choice(FUN_RESPONSES_ABSURD)
    return None


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
