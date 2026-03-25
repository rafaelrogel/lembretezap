import os
import time
import threading
from collections import defaultdict
from threading import Lock

# key -> (tokens: float, last_refill_ts: float)
_buckets: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
_lock = Lock()

def _run_janitor():
    """Prune old buckets to prevent unbounded memory growth."""
    now = time.time()
    with _lock:
        to_del = [k for k, (tokens, last) in _buckets.items() if now - last > 3600]
        for k in to_del:
            del _buckets[k]
    # Schedule next run in 1 minute
    threading.Timer(60.0, _run_janitor).start()

# FIX EXPLANATION: Janitor runs every minute to evict buckets not accessed for >1 hour, preventing memory leaks.
# Start the janitor
threading.Timer(60.0, _run_janitor).start()

def _get_default_max_per_minute() -> int:
    v = os.environ.get("RATE_LIMIT_MAX_PER_MINUTE", "").strip()
    if not v:
        return 15
    try:
        n = int(v)
        return max(5, min(300, n))  # entre 5 e 300
    except ValueError:
        return 15

DEFAULT_MAX_PER_MINUTE = 15  # usado só quando não há env; as funções usam _get_default_max_per_minute()
DEFAULT_WINDOW_SECONDS = 60


def _user_key(channel: str, chat_id: str) -> str:
    return f"{channel}:{chat_id}"


def _refill_and_consume(
    key: str,
    capacity: float,
    refill_per_second: float,
    now: float,
) -> bool:
    """
    Refill bucket, try to consume one token.
    Returns True if rate limited (no token available), False if allowed.
    """
    tokens, last = _buckets[key]
    if last == 0:
        last = now
        tokens = capacity
    elapsed = now - last
    tokens = min(capacity, tokens + elapsed * refill_per_second)
    _buckets[key] = (tokens, now)
    if tokens >= 1:
        _buckets[key] = (tokens - 1, now)
        return False
    return True


def is_rate_limited(
    channel: str,
    chat_id: str,
    max_per_minute: int | None = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> bool:
    """
    Returns True if this user has exceeded the limit (should block).
    Uses token bucket: capacity = max_per_minute, refill = max_per_minute/window_seconds per second.
    Call this when a message arrives; it records the message and returns whether to block.
    """
    if max_per_minute is None:
        max_per_minute = _get_default_max_per_minute()
    key = _user_key(channel, chat_id)
    capacity = float(max_per_minute)
    refill_per_second = capacity / window_seconds if window_seconds else capacity
    now = time.time()
    with _lock:
        return _refill_and_consume(key, capacity, refill_per_second, now)


def get_remaining(
    channel: str,
    chat_id: str,
    max_per_minute: int | None = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> int:
    """Remaining tokens (approximate). Refills bucket but does not consume a token."""
    if max_per_minute is None:
        max_per_minute = _get_default_max_per_minute()
    key = _user_key(channel, chat_id)
    capacity = float(max_per_minute)
    refill_per_second = capacity / window_seconds if window_seconds else capacity
    now = time.time()
    with _lock:
        tokens, last = _buckets[key]
        if last == 0:
            return max_per_minute
        elapsed = now - last
        tokens = min(capacity, tokens + elapsed * refill_per_second)
        _buckets[key] = (tokens, now)
        return max(0, int(tokens))


def reset_for_test(key_prefix: str = "test:") -> None:
    """Remove all buckets whose key starts with key_prefix (for tests)."""
    with _lock:
        to_del = [k for k in _buckets if k.startswith(key_prefix)]
        for k in to_del:
            del _buckets[k]


# ---------------------------------------------------------------------------
# REST API rate limiting (reuses the same token bucket)
# ---------------------------------------------------------------------------

def _get_rest_rate_limit() -> int:
    v = os.environ.get("REST_RATE_LIMIT_MINUTE", "").strip()
    if not v:
        return 60
    try:
        n = int(v)
        return max(10, min(600, n))
    except ValueError:
        return 60


def is_rest_rate_limited(api_key: str | None) -> bool:
    """Token bucket check for REST API endpoints, keyed by API key."""
    key = f"rest:{(api_key or 'anon')[:16]}"
    capacity = float(_get_rest_rate_limit())
    refill_per_second = capacity / 60.0
    now = time.time()
    with _lock:
        return _refill_and_consume(key, capacity, refill_per_second, now)
