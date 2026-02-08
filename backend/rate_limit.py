"""Rate limit per user: max N messages per minute to avoid abuse and control API cost."""

import time
from collections import defaultdict
from threading import Lock

# key -> list of timestamps (last N seconds)
_entries: dict[str, list[float]] = defaultdict(list)
_lock = Lock()

DEFAULT_MAX_PER_MINUTE = 15
DEFAULT_WINDOW_SECONDS = 60


def _user_key(channel: str, chat_id: str) -> str:
    return f"{channel}:{chat_id}"


def _prune(ts_list: list[float], window_seconds: int, now: float) -> None:
    cutoff = now - window_seconds
    while ts_list and ts_list[0] < cutoff:
        ts_list.pop(0)


def is_rate_limited(
    channel: str,
    chat_id: str,
    max_per_minute: int = DEFAULT_MAX_PER_MINUTE,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> bool:
    """
    Returns True if this user has exceeded the limit (should block).
    Call this when a message arrives; it records the message and returns whether to block.
    """
    key = _user_key(channel, chat_id)
    now = time.time()
    with _lock:
        _prune(_entries[key], window_seconds, now)
        if len(_entries[key]) >= max_per_minute:
            return True
        _entries[key].append(now)
    return False


def get_remaining(
    channel: str,
    chat_id: str,
    max_per_minute: int = DEFAULT_MAX_PER_MINUTE,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> int:
    """Remaining messages allowed in current window (for debugging)."""
    key = _user_key(channel, chat_id)
    now = time.time()
    with _lock:
        _prune(_entries[key], window_seconds, now)
        return max(0, max_per_minute - len(_entries[key]))
