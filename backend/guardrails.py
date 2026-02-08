"""Guardrails sem custo de tokens: intervalo mínimo para recorrentes e filtro de pedidos absurdos."""

import re
import random

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
