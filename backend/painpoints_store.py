"""Painpoints de clientes: registo para atendimento ao cliente contactar.

Usado quando Mimo detecta frustração/reclamação no histórico ou quando o cliente pede contato.
"""

import json
import time
from pathlib import Path

_STORE_PATH = Path.home() / ".zapista" / "security" / "client_painpoints.json"


def _digits_from_chat_id(chat_id: str) -> str:
    return "".join(c for c in str(chat_id).split("@")[0] if c.isdigit())


def _format_phone(digits: str) -> str:
    """Formato legível: 55119***9999."""
    if len(digits) >= 9:
        return digits[:5] + "***" + digits[-4:]
    return digits or "?"


def add_painpoint(chat_id: str, reason: str = "frustração/reclamação") -> None:
    """Regista um cliente como painpoint (atendimento deve contactar)."""
    try:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict] = []
        if _STORE_PATH.exists():
            try:
                entries = json.loads(_STORE_PATH.read_text())
            except Exception:
                entries = []
        digits = _digits_from_chat_id(chat_id)
        if not digits:
            return
        phone_display = _format_phone(digits)
        ts = int(time.time())
        # Evitar duplicados recentes (mesmo número nas últimas 24h)
        for e in entries:
            if e.get("digits") == digits and (ts - (e.get("timestamp") or 0)) < 86400:
                return
        entries.append({
            "digits": digits,
            "phone_display": phone_display,
            "timestamp": ts,
            "reason": (reason or "frustração/reclamação")[:100],
        })
        entries = entries[-200:]  # manter últimos 200
        _STORE_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=0))
    except Exception:
        pass


def get_painpoints() -> list[dict]:
    """Lista painpoints para #painpoints (God mode)."""
    try:
        if not _STORE_PATH.exists():
            return []
        entries = json.loads(_STORE_PATH.read_text())
        return list(reversed(entries[-50:]))  # últimos 50
    except Exception:
        return []
