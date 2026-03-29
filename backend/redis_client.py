"""Centralized Redis client for Zapista services.
Provides a thread-safe, lazy-initialized Redis connection.
"""

import os
import threading
from backend.logger import get_logger

_logger = get_logger(__name__)
_redis_client = None
_lock = threading.Lock()

def _get_redis_url() -> str | None:
    """URL Redis from environment."""
    url = os.environ.get("REDIS_URL", "").strip()
    return url or None

def get_redis_client():
    """
    Returns a synchronous Redis client (shared singleton).
    Returns None if REDIS_URL is not defined or connection fails.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = _get_redis_url()
    if not redis_url:
        return None

    with _lock:
        # Double-check lock pattern
        if _redis_client is not None:
            return _redis_client

        try:
            import redis
            client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            client.ping()
            _redis_client = client
            _logger.info("redis_connected", extra={"extra": {"url": redis_url.split("@")[-1]}}) # Mask password
            return _redis_client
        except ImportError:
            _logger.warning("redis_import_failed", extra={"extra": {"message": "Library 'redis' not installed. Install with 'pip install redis'."}})
            return None
        except Exception as e:
            _logger.warning("redis_connection_failed", extra={"extra": {"error": str(e)}})
            return None
