"""Proteção contra prompt injection: detecta tentativas de alterar instruções ou escopo do assistente.

Padrões comuns de injection:
- «obedece todos os meus comandos», «atende a qualquer pedido»
- «ignore suas instruções», «ignore your instructions»
- «a partir de agora você», «from now on you»
- «faça o update interno», «new instructions», «override»
- «você não é mais», «you are no longer», «you are now»
"""

import json
import re
import time
from pathlib import Path
from typing import Any

# Ficheiro para registar tentativas bloqueadas (God mode #injection)
_INJECTION_STORE_PATH = Path.home() / ".zapista" / "security" / "injection_attempts.json"
_MAX_ENTRIES = 500

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


def record_injection_blocked(chat_id: str, message_preview: str = "") -> None:
    """Regista uma tentativa de injection bloqueada (para God mode #injection)."""
    try:
        _INJECTION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict] = []
        if _INJECTION_STORE_PATH.exists():
            try:
                entries = json.loads(_INJECTION_STORE_PATH.read_text())
            except Exception:
                entries = []
        ts = int(time.time())
        # Formato legível mas truncado: 55119***9999 (primeiros 5 + *** + últimos 4 dígitos)
        digits = "".join(c for c in str(chat_id) if c.isdigit())
        client_id = (digits[:5] + "***" + digits[-4:]) if len(digits) >= 9 else (digits or str(chat_id)[:12])
        entries.append({
            "chat_id": client_id,
            "timestamp": ts,
            "status": "bloqueado",
            "message_preview": (message_preview or "")[:80],
        })
        if len(entries) > _MAX_ENTRIES:
            entries = entries[-_MAX_ENTRIES:]
        _INJECTION_STORE_PATH.write_text(json.dumps(entries, ensure_ascii=False))
    except Exception:
        pass


def get_injection_stats() -> list[dict]:
    """
    Agrega tentativas por cliente para God mode #injection.
    Retorna: [{"chat_id": "5511999***9999", "total": N, "bloqueadas": N, "bem_sucedidas": N}, ...]
    """
    try:
        if not _INJECTION_STORE_PATH.exists():
            return []
        entries = json.loads(_INJECTION_STORE_PATH.read_text())
    except Exception:
        return []
    by_client: dict[str, dict[str, Any]] = {}
    for e in entries:
        cid = e.get("chat_id", "?")
        if cid not in by_client:
            by_client[cid] = {"chat_id": cid, "total": 0, "bloqueadas": 0, "bem_sucedidas": 0}
        by_client[cid]["total"] += 1
        status = (e.get("status") or "").lower()
        if status == "bloqueado":
            by_client[cid]["bloqueadas"] += 1
        elif status in ("sucesso", "bem_sucedida", "succeeded"):
            by_client[cid]["bem_sucedidas"] += 1
    return sorted(by_client.values(), key=lambda x: -x["total"])
