from datetime import UTC, datetime, timedelta

from hotel.web.rate_limit import RateLimiter

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


def test_requests_beyond_the_limit_wait_for_the_next_window():
    limiter = RateLimiter(limit=3, window=timedelta(minutes=1))
    assert [limiter.hit("a", NOW) for _ in range(3)] == [0, 0, 0]
    assert limiter.hit("a", NOW + timedelta(seconds=20)) == 41  # seconds left, rounded up
    assert limiter.hit("b", NOW) == 0  # keys are counted separately
    assert limiter.hit("a", NOW + timedelta(minutes=1)) == 0  # a new window


def test_old_windows_are_forgotten_when_there_are_many_keys():
    limiter = RateLimiter(limit=1, window=timedelta(minutes=1))
    for i in range(10_001):
        limiter.hit(str(i), NOW)
    limiter.hit("new", NOW + timedelta(minutes=2))
    assert len(limiter._counters) == 1
