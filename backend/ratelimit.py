"""
Small in-memory sliding-window rate limiter for public endpoints that are not
covered by account quotas (e.g. the withdrawal form, which by law cannot require
login). In-memory is enough with a single server process (see the Dockerfile);
with several processes or machines it should move to a shared store (Redis).
"""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:
                self._forget_idle(now)
            return True

    def _forget_idle(self, now: float):
        """Drop keys whose LAST hit is outside the window. Their deques are only pruned when
        the same key comes back, so "empty deque" alone would never free idle keys."""
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
            del self._hits[key]
