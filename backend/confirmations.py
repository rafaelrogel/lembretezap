"""Estado de confirmações pendentes (1=sim 2=não). Sem botões; texto numerado.

Persistência:
- Se REDIS_URL definido: usa Redis (resiliente a restarts do gateway)
- Senão: fallback para memória (desenvolvimento local)

TODO: Após WhatsApp Business API, use buttons: sendButtons(['Confirmar','Cancelar']).
"""

import json
import os
import time
from typing import Any

_PENDING: dict[str, dict[str, Any]] = {}  # fallback memória
_EXPIRY_SECONDS = 300  # 5 min
_REDIS_KEY_PREFIX = "zapista:pending:"

# Cliente Redis partilhado
_redis_client = None


def _get_redis_url() -> str | None:
    """URL Redis a partir do ambiente."""
    url = os.environ.get("REDIS_URL", "").strip()
    return url or None


def _get_redis_client():
    """Retorna cliente Redis síncrono (para uso em sync code)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = _get_redis_url()
    if not redis_url:
        return None
    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        # Testar conexão
        _redis_client.ping()
        return _redis_client
    except Exception:
        return None


def _key(channel: str, chat_id: str) -> str:
    return f"{channel}:{chat_id}"


def _redis_key(channel: str, chat_id: str) -> str:
    return f"{_REDIS_KEY_PREFIX}{_key(channel, chat_id)}"


def set_pending(channel: str, chat_id: str, action: str, payload: dict[str, Any] | None = None) -> None:
    """Regista confirmação pendente. Resposta do user '1' ou '2' resolve."""
    data = {
        "action": action,
        "payload": payload or {},
        "ts": time.time(),
    }
    
    # Tentar Redis primeiro
    client = _get_redis_client()
    if client:
        try:
            client.setex(
                _redis_key(channel, chat_id),
                _EXPIRY_SECONDS,
                json.dumps(data, ensure_ascii=False)
            )
            return
        except Exception:
            pass  # Fallback para memória
    
    # Fallback: memória
    _PENDING[_key(channel, chat_id)] = data


def get_pending(channel: str, chat_id: str) -> dict[str, Any] | None:
    """Obtém confirmação pendente se existir e não expirada."""
    # Tentar Redis primeiro
    client = _get_redis_client()
    if client:
        try:
            data = client.get(_redis_key(channel, chat_id))
            if data:
                return json.loads(data)
            return None
        except Exception:
            pass  # Fallback para memória
    
    # Fallback: memória
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
    # Tentar Redis primeiro
    client = _get_redis_client()
    if client:
        try:
            client.delete(_redis_key(channel, chat_id))
        except Exception:
            pass
    
    # Limpar também da memória (caso tenha sido criado lá)
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
