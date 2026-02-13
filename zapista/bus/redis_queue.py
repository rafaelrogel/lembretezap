"""Fila Redis para mensagens outbound (deploy com Redis).

Quando REDIS_URL está definido, o MessageBus usa Redis como fila durável:
- Mensagens time-sensitive (lembretes) vão para zapista:outbound:high (prioridade)
- Respostas do agente vão para zapista:outbound:normal
- Consumer faz BLPOP high, normal (lembretes saem primeiro)

Dedup inbound: message_id em zapista:dedup:inbound:{id} com TTL 24h.

Conexão Redis: cliente partilhado (connection pool) por processo, em vez de
criar/fechar por operação — reduz latência e CPU sob carga.
"""

import json
import os
from typing import TYPE_CHECKING, Any

from zapista.bus.events import OutboundMessage

if TYPE_CHECKING:
    from redis.asyncio import Redis

QUEUE_KEY = "zapista:outbound"  # legado; uso QUEUE_KEY_HIGH / QUEUE_KEY_NORMAL
QUEUE_KEY_HIGH = "zapista:outbound:high"  # lembretes, entregas time-sensitive
QUEUE_KEY_NORMAL = "zapista:outbound:normal"
BLOCK_TIMEOUT_SECONDS = 5
DEDUP_INBOUND_TTL = 24 * 3600  # 24 horas
DEDUP_KEY_PREFIX = "zapista:dedup:inbound:"

# Cliente Redis partilhado (connection pool) — evita criar/fechar por operação
_redis_client: "Redis | None" = None
_redis_client_url: str | None = None


def _serialize_message(msg: OutboundMessage) -> str:
    """OutboundMessage -> JSON string (apenas tipos serializáveis)."""
    # metadata pode ter valores não-JSON; normalizar para str quando necessário
    meta = {}
    for k, v in (msg.metadata or {}).items():
        try:
            json.dumps(v)
            meta[k] = v
        except (TypeError, ValueError):
            meta[k] = str(v)
    payload = {
        "channel": msg.channel,
        "chat_id": msg.chat_id,
        "content": msg.content,
        "reply_to": msg.reply_to,
        "media": list(msg.media or []),
        "metadata": meta,
    }
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_message(data: str) -> OutboundMessage | None:
    """JSON string -> OutboundMessage ou None se inválido."""
    try:
        d = json.loads(data)
        return OutboundMessage(
            channel=str(d.get("channel", "")),
            chat_id=str(d.get("chat_id", "")),
            content=str(d.get("content", "")),
            reply_to=d.get("reply_to") and str(d["reply_to"]) or None,
            media=list(d.get("media") or []),
            metadata=dict(d.get("metadata") or {}),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def get_redis_url() -> str | None:
    """URL Redis a partir do ambiente (REDIS_URL). None se não configurado."""
    url = os.environ.get("REDIS_URL", "").strip()
    return url or None


def _is_high_priority(msg: OutboundMessage) -> bool:
    """True se metadata.priority == 'high' (lembretes, entregas time-sensitive)."""
    return (msg.metadata or {}).get("priority") == "high"


async def _get_redis_client(redis_url: str) -> "Redis | None":
    """
    Retorna cliente Redis partilhado (connection pool) para o processo.
    Lazy init na primeira utilização; reutiliza conexões em vez de criar/fechar por op.
    """
    global _redis_client, _redis_client_url
    try:
        from redis.asyncio import Redis
    except ImportError:
        return None
    if _redis_client is not None and _redis_client_url == redis_url:
        return _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    _redis_client = Redis.from_url(redis_url, decode_responses=True)
    _redis_client_url = redis_url
    return _redis_client


async def close_redis_pool() -> None:
    """Fecha o cliente Redis partilhado. Opcional no shutdown do processo."""
    global _redis_client, _redis_client_url
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        _redis_client_url = None


async def push_outbound(redis_url: str, msg: OutboundMessage) -> bool:
    """
    Coloca uma mensagem outbound na fila Redis (RPUSH).
    Prioridade high (metadata) → fila high; caso contrário → fila normal.
    Retorna True se enviado, False em erro.
    """
    client = await _get_redis_client(redis_url)
    if not client:
        return False
    try:
        key = QUEUE_KEY_HIGH if _is_high_priority(msg) else QUEUE_KEY_NORMAL
        await client.rpush(key, _serialize_message(msg))
        return True
    except Exception:
        return False


async def pop_outbound_blocking(redis_url: str) -> OutboundMessage | None:
    """
    Bloqueia à espera de mensagem. BLPOP com high primeiro, depois normal.
    Retorna OutboundMessage ou None (timeout/erro).
    Usa conexão persistente do pool; BLPOP bloqueia na mesma conexão.
    """
    client = await _get_redis_client(redis_url)
    if not client:
        return None
    try:
        result = await client.blpop(
            [QUEUE_KEY_HIGH, QUEUE_KEY_NORMAL],
            timeout=BLOCK_TIMEOUT_SECONDS,
        )
        if not result or not isinstance(result, (list, tuple)) or len(result) < 2:
            return None
        _, value = result
        if value is None or not isinstance(value, str):
            return None
        return _deserialize_message(value)
    except Exception:
        return None


async def is_inbound_duplicate_or_record(redis_url: str, message_id: str) -> bool:
    """
    Verifica se message_id já foi processado; se não, regista com TTL 24h.
    Retorna True se duplicado, False se nova (e regista).
    Usa SET NX EX: se a chave já existir, duplicado.
    """
    if not message_id or not message_id.strip():
        return False
    client = await _get_redis_client(redis_url)
    if not client:
        return False
    key = f"{DEDUP_KEY_PREFIX}{message_id.strip()[:128]}"
    try:
        was_set = await client.set(key, "1", nx=True, ex=DEDUP_INBOUND_TTL)
        return not was_set  # True = duplicado, False = novo
    except Exception:
        return False


def is_redis_available() -> bool:
    """True se REDIS_URL está definido e redis está instalado."""
    if not get_redis_url():
        return False
    try:
        import redis  # noqa: F401
        return True
    except ImportError:
        return False
