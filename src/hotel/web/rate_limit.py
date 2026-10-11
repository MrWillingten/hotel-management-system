"""A small in-memory rate limiter for the JSON API (story 6.3).

Fixed windows: each key (a token, or an address sending bad tokens) may make
`limit` requests per `window`; the counter starts again in the next window.
The application runs as one process (Waitress threads), so a dictionary
protected by a lock is enough; a restart simply resets the counters.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta


class RateLimiter:
    def __init__(self, limit: int, window: timedelta) -> None:
        self.limit = limit
        self.window = window
        self._lock = threading.Lock()
        self._counters: dict[str, tuple[datetime, int]] = {}

    def hit(self, key: str, now: datetime) -> int:
        """Count one request; returns 0 if allowed, else the seconds to wait."""
        with self._lock:
            if len(self._counters) > 10_000:  # forget finished windows now and then
                self._counters = {
                    k: v for k, v in self._counters.items() if now - v[0] < self.window
                }
            start, count = self._counters.get(key, (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            if count >= self.limit:
                return max(1, int((start + self.window - now).total_seconds()) + 1)
            self._counters[key] = (start, count + 1)
            return 0
