"""Circuit breaker for external calls (e.g. LLM API).

When the circuit is open (too many failures), the system can operate in degraded
mode (e.g. only structured command parsing) instead of cascading failures.
"""

import time
from threading import Lock
from typing import Literal

State = Literal["closed", "open", "half_open"]


class CircuitBreaker:
    """
    Simple circuit breaker: closed -> open after failure_threshold failures;
    open -> half_open after recovery_timeout_seconds; half_open -> closed on success, open on failure.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._state: State = "closed"
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = Lock()

    def is_open(self) -> bool:
        """
        Returns True if the circuit is open (calls should be skipped).
        Transitions open -> half_open when recovery_timeout has passed.
        """
        with self._lock:
            if self._state == "closed":
                return False
            if self._state == "open":
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout_seconds:
                    self._state = "half_open"
                else:
                    return True
            return False  # half_open: allow one call through

    def record_success(self) -> None:
        """Call after a successful external call."""
        with self._lock:
            self._failure_count = 0
            self._state = "closed"

    def record_failure(self) -> None:
        """Call after a failed external call."""
        with self._lock:
            self._last_failure_time = time.monotonic()
            if self._state == "half_open":
                self._state = "open"
                self._failure_count = self.failure_threshold
            else:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = "open"
