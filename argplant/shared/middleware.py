"""IP-based rate limiter and X-Stale header injection middleware."""

import time
from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from argplant.shared.config import settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """IP-based sliding-window rate limiter using Redis INCR + EXPIRE.

    Returns 429 with Retry-After header when the limit is exceeded.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._redis: aioredis.Redis | None = None

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip rate limiting if no Redis is available (graceful degradation)
        try:
            redis = await self._ensure_redis()
            client_ip = _get_client_ip(request)
            key = f"rate:{client_ip}:{_window_id()}"

            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)

            limit = settings.RATE_LIMIT_REQUESTS
            if count > limit:
                ttl = await redis.ttl(key)
                retry_after = max(ttl, 1)
                return Response(
                    content='{"detail":"Too many requests"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception:
            # If Redis is down, skip rate limiting
            pass

        response = await call_next(request)
        return response


def add_stale_header(response: Response) -> None:
    """Inject X-Stale: true header to signal that the response contains stale data."""
    response.headers["X-Stale"] = "true"


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For if behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    if client:
        return client.host
    return "unknown"


def _window_id() -> int:
    """Return the current rate-limit window identifier (UTC epoch rounded to window size)."""
    now = int(time.time())
    return now // settings.RATE_LIMIT_WINDOW_SECONDS
