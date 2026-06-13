"""Rate limiting middleware for FastAPI."""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from redis.asyncio import Redis
from app.core.dependencies import redis_client


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
        except Exception:
            # If Redis is down, allow the request
            pass

        return await call_next(request)
