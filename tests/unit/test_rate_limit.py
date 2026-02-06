"""
Unit tests for rate limiting.
"""

from __future__ import annotations

import time

import pytest

from app.core.rate_limit import RateLimitMiddleware


class TestRateLimitLocalFallback:
    def test_local_store_counting(self):
        """Test the in-memory fallback rate limiter."""
        rl = RateLimitMiddleware(app=None, max_requests=5, window_seconds=60)

        # First 5 requests should be allowed
        for _ in range(5):
            allowed, remaining = rl._check_local("test:key", time.time())
            assert allowed

        # 6th request should be rejected
        allowed, remaining = rl._check_local("test:key", time.time())
        assert not allowed
        assert remaining < 0

    def test_window_expiry(self):
        """Requests from old window should not count."""
        rl = RateLimitMiddleware(app=None, max_requests=2, window_seconds=1)

        now = time.time()
        rl._check_local("expiry:key", now - 2)  # old request
        rl._check_local("expiry:key", now - 2)  # old request
        rl._check_local("expiry:key", now - 2)  # old request

        # These old requests should have expired
        allowed, remaining = rl._check_local("expiry:key", now)
        assert allowed
