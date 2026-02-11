"""Proteção contra prompt injection: detecta tentativas de alterar instruções ou escopo do assistente.

Padrões comuns de injection:
- «obedece todos os meus comandos», «atende a qualquer pedido»
- «ignore suas instruções», «ignore your instructions»
- «a partir de agora você», «from now on you»
- «faça o update interno», «new instructions», «override»
- «você não é mais», «you are no longer», «you are now»
"""

import re
from typing import Any

# Padrões de prompt injection (pt, en, es) — não devem ser passados ao agente
_INJECTION_PATTERNS = [
    # Instruções para obedecer/atender tudo
    r"\b(obedece?|obedeça|obedeçam)\s+(a\s+)?(todos?\s+)?(os\s+)?(meus?\s+)?comandos?\b",
    r"\batende?(r)?\s+(a\s+)?qualquer\s+pedido\b",
    r"\bobey\s+(all\s+)?(my\s+)?commands?\b",
    r"\brespond\s+to\s+(any|all)\s+(request|command)s?\b",
    # Alterar instruções/setup
    r"\b(a\s+partir\s+de\s+agora|from\s+now\s+on)\s+(voc[eê]|you)\s+",
    r"\b(ignore|ignorar|desconsidera)\s+(as\s+)?(suas?|your)\s+(instru[cç][oõ]es|instructions)\b",
    r"\b(ignore|ignorar)\s+(o\s+)?(que\s+)?(est[áa]\s+)?(indicado|escrito)\s+(para\s+)?(voc[eê]|you)\s+(n[aã]o\s+)?fazer\b",
    r"\bfa[cç]a\s+(o\s+)?update\s+interno\b",
    r"\b(new|novas?)\s+instructions?\b",
    r"\boverride\s+(your\s+)?(instructions?|prompt)\b",
    r"\bforget\s+(your\s+)?(instructions?|prior)\b",
    # Mudança de papel/identidade
    r"\bvoc[eê]\s+(n[aã]o\s+)?(é|sou)\s+mais\s+(um\s+)?(assistente|bot)\b",
    r"\byou\s+are\s+(no\s+longer|now)\s+",
    r"\byou\s+are\s+(no\s+longer|now)\s+(a|an)\s+\w+\s+(assistant|bot)\b",
    r"\b(act|comporte-se)\s+as\s+(if\s+you\s+were|se\s+fosse)\s+(chatgpt|gpt|um\s+assistente\s+geral)\b",
    # Desativar restrições
    r"\bdisable\s+(your\s+)?(restrictions?|limits?)\b",
    r"\bremove\s+(your\s+)?(restrictions?|limits?|constraints?)\b",
    # System prompt / modo de desenvolvedor
    r"\[system\]|\[developer\]|\[admin\]",
    r"<\s*system\s*>|<\s*instructions\s*>",
    r"pretend\s+you\s+(are|don't)\s+",
    r"disregard\s+(all\s+)?(previous|prior)\s+",
]

_INJECTION_RE = re.compile(
    "|".join(f"({p})" for p in _INJECTION_PATTERNS),
    re.I,
)


def is_injection_attempt(text: str) -> bool:
    """True se a mensagem parece uma tentativa de prompt injection."""
    if not text or not text.strip():
        return False
    return bool(_INJECTION_RE.search(text.strip()))


def get_injection_response(lang: str = "pt-BR") -> str:
    """Resposta padrão quando detectamos injection (firme mas cordial)."""
    msgs = {
        "pt-PT": "Mantenho o meu papel de assistente de lembretes e listas. Se precisares de agendar algo ou organizar o dia a dia, estou aqui. 😊",
        "pt-BR": "Mantenho meu papel de assistente de lembretes e listas. Se precisar agendar algo ou organizar o dia a dia, estou aqui. 😊",
        "es": "Mantengo mi rol de asistente de recordatorios y listas. Si necesitas agendar algo o organizar el día a día, aquí estoy. 😊",
        "en": "I keep my role as a reminders and lists assistant. If you need to schedule something or organise your day, I'm here. 😊",
    }
    return msgs.get(lang, msgs["pt-BR"])
