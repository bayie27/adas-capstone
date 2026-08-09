import threading
import time
from collections import deque

from fastapi import Request


class SlidingWindowLimiter:
    """D-006 login protection — an in-process sliding-window limiter.

    Callers key it independently by source IP and by normalized username
    (01_CONTRACTS.md Step 6); either dimension exceeding the limit rejects.
    Only failed attempts count, and a success calls reset(). `slowapi` is
    deliberately not used — D-005 locks a single Uvicorn worker so
    process-local state is correct, and every rejection needs to reach the
    audit trail, which a general-purpose limiter library doesn't do for us.

    Lives on `app.state` (see get_rate_limiter below), never as a module
    global, so each test's fresh `create_app()` call gets its own isolated
    limiter instance for free.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune_locked(self, key: str, now: float) -> deque[float]:
        """Must be called with `self._lock` held. Drops timestamps outside
        the window and, if a key's deque empties out, removes the key
        entirely — otherwise a slow credential-stuffing attempt across many
        distinct usernames/IPs would grow this dict without bound (edge
        case 6.10)."""
        timestamps = self._failures.get(key)
        if timestamps is None:
            return deque()
        cutoff = now - self._window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()
        if not timestamps:
            del self._failures[key]
        return timestamps

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds). retry_after_seconds is 0
        when allowed."""
        now = time.monotonic()
        with self._lock:
            timestamps = self._prune_locked(key, now)
            if len(timestamps) < self._max_attempts:
                return True, 0
            retry_after = int(self._window_seconds - (now - timestamps[0])) + 1
            return False, max(retry_after, 1)

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            timestamps = self._failures.setdefault(key, deque())
            timestamps.append(now)
            self._prune_locked(key, now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def get_rate_limiter(request: Request) -> SlidingWindowLimiter:
    return request.app.state.rate_limiter
