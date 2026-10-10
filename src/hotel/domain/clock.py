"""Where "now" comes from.

Rules such as "less than 48 hours before arrival" depend on the current time.
Services never call datetime.now() themselves; they ask a Clock. Production
uses SystemClock, tests use FixedClock so results are always reproducible.

Instants are timezone-aware and kept in UTC. Calendar days ("today") are
computed in the hotel's own time zone, Africa/Tunis by default.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, timedelta, tzinfo


class Clock(ABC):
    def __init__(self, hotel_tz: tzinfo) -> None:
        self.hotel_tz = hotel_tz

    @abstractmethod
    def now(self) -> datetime:
        """The current instant, timezone-aware, in UTC."""

    def local_now(self) -> datetime:
        return self.now().astimezone(self.hotel_tz)

    def today(self) -> date:
        """Today's date at the hotel (not in UTC, not on the server's clock)."""
        return self.local_now().date()


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """A clock that only moves when a test tells it to."""

    def __init__(self, instant: datetime, hotel_tz: tzinfo) -> None:
        super().__init__(hotel_tz)
        if instant.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._instant = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._instant

    def advance(self, delta: timedelta) -> None:
        self._instant += delta
