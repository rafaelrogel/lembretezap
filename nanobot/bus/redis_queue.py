"""Fila Redis para mensagens outbound (deploy com Redis).

Quando REDIS_URL está definido, o MessageBus pode usar Redis como fila durável:
- publish_outbound faz RPUSH na lista nanobot:outbound
- Um consumer (gateway) faz BRPOP e coloca na queue in-memory para dispatch.

Uso opcional: sem REDIS_URL o bus continua só em memória.
"""

import json
import os
from typing import Any

from nanobot.bus.events import OutboundMessage

QUEUE_KEY = "nanobot:outbound"
BLOCK_TIMEOUT_SECONDS = 5


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


async def push_outbound(redis_url: str, msg: OutboundMessage) -> bool:
    """
    Coloca uma mensagem outbound na fila Redis (RPUSH).
    Retorna True se enviado, False em erro.
    """
    try:
        from redis.asyncio import Redis
    except ImportError:
        return False
    client: Redis | None = None
    try:
        client = Redis.from_url(redis_url, decode_responses=True)
        await client.rpush(QUEUE_KEY, _serialize_message(msg))
        return True
    except Exception:
        return False
    finally:
        if client:
            await client.aclose()


async def pop_outbound_blocking(redis_url: str) -> OutboundMessage | None:
    """
    Bloqueia até BLOCK_TIMEOUT_SECONDS à espera de uma mensagem (BRPOP).
    Retorna OutboundMessage ou None (timeout/erro).
    """
    try:
        from redis.asyncio import Redis
    except ImportError:
        return None
    client: Redis | None = None
    try:
        client = Redis.from_url(redis_url, decode_responses=True)
        result = await client.brpop(QUEUE_KEY, timeout=BLOCK_TIMEOUT_SECONDS)
        if not result or not isinstance(result, (list, tuple)) or len(result) < 2:
            return None
        # brpop returns (key, value)
        _, value = result
        if value is None or not isinstance(value, str):
            return None
        return _deserialize_message(value)
    except Exception:
        return None
    finally:
        if client:
            await client.aclose()


def is_redis_available() -> bool:
    """True se REDIS_URL está definido e redis está instalado."""
    if not get_redis_url():
        return False
    try:
        import redis  # noqa: F401
        return True
    except ImportError:
        return False
