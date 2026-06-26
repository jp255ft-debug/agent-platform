"""Rate limiting middleware for FastAPI."""
import logging

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that applies rate limiting to API requests."""

    def __init__(self, app, redis: Redis | None = None, max_requests: int = 100, window: int = 60):
        super().__init__(app)
        self._redis = redis
        self._max_requests = max_requests
        self._window = window

    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply rate limiting based on client IP."""
        if not self._redis:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{request.url.path}"

        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, self._window)

            if current > self._max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(self._window)},
                )
        except HTTPException:
            raise
        except Exception as e:
            # If Redis is down, allow the request (fail-open)
            logger.warning("Redis unavailable, rate limiting disabled: %s", e)

        return await call_next(request)
