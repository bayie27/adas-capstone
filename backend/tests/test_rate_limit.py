"""
Unit tests for app.core.rate_limit.SlidingWindowLimiter — D-006 login
protection and edge case 6.10 (unbounded key growth).
"""

import time

from app.core.rate_limit import SlidingWindowLimiter


class TestSlidingWindowLimiter:
    def test_allows_up_to_max_attempts(self):
        limiter = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            allowed, retry_after = limiter.check("k")
            assert allowed is True
            assert retry_after == 0
            limiter.record_failure("k")

    def test_rejects_the_nth_plus_one_attempt(self):
        limiter = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            limiter.record_failure("k")
        allowed, retry_after = limiter.check("k")
        assert allowed is False
        assert retry_after > 0

    def test_reset_clears_the_key(self):
        limiter = SlidingWindowLimiter(max_attempts=1, window_seconds=60)
        limiter.record_failure("k")
        assert limiter.check("k") == (False, limiter.check("k")[1])
        limiter.reset("k")
        allowed, retry_after = limiter.check("k")
        assert allowed is True
        assert retry_after == 0

    def test_window_expiry_allows_again(self):
        limiter = SlidingWindowLimiter(max_attempts=1, window_seconds=1)
        limiter.record_failure("k")
        assert limiter.check("k")[0] is False
        time.sleep(1.1)
        assert limiter.check("k")[0] is True

    def test_keys_are_independent(self):
        limiter = SlidingWindowLimiter(max_attempts=1, window_seconds=60)
        limiter.record_failure("a")
        allowed_a, _ = limiter.check("a")
        allowed_b, _ = limiter.check("b")
        assert allowed_a is False
        assert allowed_b is True

    def test_expired_keys_are_pruned_not_retained(self):
        """Edge case 6.10 — a slow sweep across many distinct keys must not
        grow the internal dict unboundedly."""
        limiter = SlidingWindowLimiter(max_attempts=5, window_seconds=1)
        for i in range(50):
            limiter.record_failure(f"key-{i}")
        assert len(limiter._failures) == 50

        time.sleep(1.1)
        # Checking (or recording against) each key prunes it once its
        # window has fully elapsed and it has no remaining timestamps.
        for i in range(50):
            limiter.check(f"key-{i}")
        assert len(limiter._failures) == 0
