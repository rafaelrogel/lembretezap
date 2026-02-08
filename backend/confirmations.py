"""Estado de confirmações pendentes (1=sim 2=não). Sem botões; texto numerado.
TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']).
"""

import time
from typing import Any

_PENDING: dict[tuple[str, str], dict[str, Any]] = {}
_EXPIRY_SECONDS = 300  # 5 min


def _key(channel: str, chat_id: str) -> tuple[str, str]:
    return (channel, str(chat_id))


def set_pending(channel: str, chat_id: str, action: str, payload: dict[str, Any] | None = None) -> None:
    """Regista confirmação pendente. Resposta do user '1' ou '2' resolve."""
    _PENDING[_key(channel, chat_id)] = {
        "action": action,
        "payload": payload or {},
        "ts": time.time(),
    }


def get_pending(channel: str, chat_id: str) -> dict[str, Any] | None:
    """Obtém confirmação pendente se existir e não expirada."""
    key = _key(channel, chat_id)
    entry = _PENDING.get(key)
    if not entry:
        return None
    if time.time() - entry["ts"] > _EXPIRY_SECONDS:
        del _PENDING[key]
        return None
    return entry


def clear_pending(channel: str, chat_id: str) -> None:
    """Remove confirmação pendente."""
    _PENDING.pop(_key(channel, chat_id), None)


def is_confirm_reply(content: str) -> bool:
    """True se a mensagem é resposta de confirmação (1, 2, sim, não)."""
    t = (content or "").strip().lower()
    return t in ("1", "2", "sim", "s", "não", "nao", "n", "yes", "no")


def is_confirm_yes(content: str) -> bool:
    """True se user confirmou (1, sim, s, yes)."""
    t = (content or "").strip().lower()
    return t in ("1", "sim", "s", "yes", "y")


def is_confirm_no(content: str) -> bool:
    """True se user recusou (2, não, n, no)."""
    t = (content or "").strip().lower()
    return t in ("2", "não", "nao", "n", "no")
