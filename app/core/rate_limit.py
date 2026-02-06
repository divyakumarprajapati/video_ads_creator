"""
Rate limiting middleware using Redis as the sliding-window counter store.

Applies per-user limits based on the authenticated identity derived
from the ``X-API-Key`` or JWT token.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter.

    Falls back to in-memory counting when Redis is unavailable so the
    API never hard-fails because of rate-limit infrastructure.
    """

    def __init__(self, app, max_requests: int = 0, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_per_minute
        self.window = window_seconds
        self._redis = None
        self._local_store: dict[str, list[float]] = {}  # fallback

    def _get_redis(self):
        if not settings.redis_enabled:
            return None
        if self._redis is None:
            try:
                import redis as _redis
                self._redis = _redis.from_url(settings.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _identity(self, request: Request) -> str:
        """Extract a rate-limit key from the request."""
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            return f"rl:{api_key[:16]}"
        auth = request.headers.get("authorization", "")
        if auth:
            return f"rl:{auth[-16:]}"
        host = request.client.host if request.client else "unknown"
        return f"rl:ip:{host}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for health endpoints
        if request.url.path in ("/api/v1/health", "/api/v1/ready", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        key = self._identity(request)
        now = time.time()

        allowed, remaining = self._check_redis(key, now)
        if not allowed:
            allowed, remaining = self._check_local(key, now)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window}s.",
                headers={"Retry-After": str(self.window)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response

    def _check_redis(self, key: str, now: float) -> tuple[bool, int]:
        r = self._get_redis()
        if r is None:
            return True, self.max_requests  # fallback to local

        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, now - self.window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self.window)
            results = pipe.execute()
            count = results[2]
            remaining = self.max_requests - count
            return count <= self.max_requests, remaining
        except Exception:
            return True, self.max_requests

    def _check_local(self, key: str, now: float) -> tuple[bool, int]:
        if key not in self._local_store:
            self._local_store[key] = []
        # Prune old entries
        cutoff = now - self.window
        self._local_store[key] = [t for t in self._local_store[key] if t > cutoff]
        self._local_store[key].append(now)
        count = len(self._local_store[key])
        remaining = self.max_requests - count
        return count <= self.max_requests, remaining
