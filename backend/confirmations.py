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

from backend.redis_client import get_redis_client

_PENDING: dict[str, dict[str, Any]] = {}  # fallback memória
_EXPIRY_SECONDS = 300  # 5 min
_REDIS_KEY_PREFIX = "zapista:pending:"


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
    client = get_redis_client()
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
    client = get_redis_client()
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
    client = get_redis_client()
    if client:
        try:
            client.delete(_redis_key(channel, chat_id))
        except Exception:
            pass
    
    # Limpar também da memória (caso tenha sido criado lá)
    _PENDING.pop(_key(channel, chat_id), None)


def is_confirm_reply(content: str) -> bool:
    """True se a mensagem é resposta de confirmação (1, 2, sim, não, etc.)."""
    t = (content or "").strip().lower()
    # Padrões numéricos e básicos
    if t in ("1", "2"):
        return True
    
    # Prefixos ou palavras isoladas comuns em 4 línguas
    # PT: sim, s, pode, claro, ok, bora, concordo, perfeito, não, n, cancela
    # EN: yes, y, sure, ok, right, agree, perfect, no, n, cancel
    # ES: sí, si, s, claro, de acuerdo, vale, no, n, cancela
    yes_words = {"sim", "s", "pode", "pode ser", "claro", "ok", "bora", "concordo", "perfeito", "yes", "y", "sure", "right", "agree", "perfect", "si", "sí", "vale", "de acuerdo", "bueno", "dale"}
    no_words = {"nao", "não", "n", "no", "cancela", "cancelar", "stop", "parar", "negative", "negativo", "interromper"}
    
    # Normalização simples (remove pontuação e acentos básicos)
    import unicodedata
    t_norm = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t_root = t_norm.rstrip(".!?")
    
    return t_root in yes_words or t_root in no_words or t in yes_words or t in no_words


def is_confirm_yes(content: str) -> bool:
    """True se user confirmou (1, sim, s, yes, pode, etc.)."""
    t = (content or "").strip().lower()
    if t == "1":
        return True
    yes_words = {"sim", "s", "pode", "pode ser", "claro", "ok", "bora", "concordo", "perfeito", "yes", "y", "sure", "right", "agree", "perfect", "si", "sí", "vale", "de acuerdo", "bueno", "dale", "faca isso", "faz isso"}
    
    import unicodedata
    t_norm = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t_root = t_norm.rstrip(".!?")
    
    return t in yes_words or t_root in yes_words


def is_confirm_no(content: str) -> bool:
    """True se user recusou (2, não, n, no, cancela, etc.)."""
    t = (content or "").strip().lower()
    if t == "2":
        return True
    no_words = {"nao", "não", "n", "no", "cancela", "cancelar", "stop", "parar", "negative", "negativo", "interromper"}
    
    import unicodedata
    t_norm = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t_root = t_norm.rstrip(".!?")
    
    return t in no_words or t_root in no_words
