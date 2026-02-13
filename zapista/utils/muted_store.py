"""Mute/penalidade por número: níveis 1–6 com duração crescente.

1º: 15 min, 2º: 30 min, 3º: 2 h, 4º: 24 h, 5º: 7 dias, 6º: bloqueio permanente.
Persistido em muted.json no data dir.
"""

import json
import time
from pathlib import Path

from zapista.config.loader import get_data_dir

_FILENAME = "muted.json"

# (count 1–6) -> (duration_seconds, duration_label, user_message_template)
_LEVELS: list[tuple[int, str, str]] = [
    (15 * 60, "15 minutos", "Recebeste a 1ª punição. Ficas sem resposta durante 15 minutos."),
    (30 * 60, "30 minutos", "Recebeste a 2ª punição. Ficas sem resposta durante 30 minutos."),
    (2 * 3600, "2 horas", "Recebeste a 3ª punição. Ficas sem resposta durante 2 horas."),
    (24 * 3600, "24 horas", "Recebeste a 4ª punição. Ficas sem resposta durante 24 horas."),
    (7 * 24 * 3600, "7 dias", "Recebeste a 5ª punição. Ficas sem resposta durante 7 dias."),
    (0, "permanente", "Não fazes mais parte do sistema."),
]


def _path() -> Path:
    return get_data_dir() / _FILENAME


def _normalize(phone: str) -> str:
    return "".join(c for c in str(phone or "") if c.isdigit())


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_muted(phone: str) -> bool:
    """
    True se o número está atualmente muted (dentro do tempo) ou bloqueado (6º mute).
    Quando o tempo expira, deixa de estar muted mas o count mantém-se para o próximo mute.
    """
    digits = _normalize(phone)
    if not digits:
        return False
    data = _load()
    entry = data.get(digits)
    if not entry:
        return False
    count = entry.get("count", 0)
    if count >= 6:
        return True  # bloqueio permanente
    until = entry.get("muted_until_ts")
    if until is None:
        return False
    return time.time() < until


def apply_mute(phone: str) -> tuple[str, int, str]:
    """
    Aplica o próximo nível de mute ao número.
    Retorna (mensagem para enviar ao utilizador, count 1–6, texto curto para o admin).
    """
    digits = _normalize(phone)
    if not digits:
        return ("", 0, "Número inválido.")
    data = _load()
    entry = data.get(digits) or {"count": 0, "muted_until_ts": None}
    count = min(entry.get("count", 0) + 1, 6)
    idx = count - 1
    duration_sec, duration_label, user_message = _LEVELS[idx]
    now = time.time()
    if count >= 6:
        muted_until_ts = None  # permanente
    else:
        muted_until_ts = now + duration_sec
    data[digits] = {"count": count, "muted_until_ts": muted_until_ts}
    _save(data)
    admin_msg = f"Mute aplicado: {count}ª punição, {duration_label}."
    return (user_message, count, admin_msg)
