"""Unit tests for RateLimitMiddleware."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, HTTPException, status
from starlette.responses import JSONResponse

from app.api.v1.middleware.rate_limit_middleware import RateLimitMiddleware


@pytest.fixture
def mock_app():
    """Create a mock ASGI app."""
    app = MagicMock()
    return app


@pytest.fixture
def mock_redis():
    """Create a mock Redis async client."""
    redis = MagicMock()
    redis.incr = AsyncMock()
    redis.expire = AsyncMock()
    return redis


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/agents"
    request.client.host = "192.168.1.100"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""
    async def call_next(request):
        return JSONResponse(content={"status": "ok"}, status_code=200)
    return call_next


class TestRateLimitMiddlewareInitialization:
    """Test RateLimitMiddleware initialization."""

    def test_init_with_defaults(self, mock_app):
        middleware = RateLimitMiddleware(mock_app)
        assert middleware._redis is None
        assert middleware._max_requests == 100
        assert middleware._window == 60

    def test_init_with_custom_values(self, mock_app, mock_redis):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis, max_requests=50, window=30)
        assert middleware._redis == mock_redis
        assert middleware._max_requests == 50
        assert middleware._window == 30


class TestDispatch:
    """Test dispatch method."""

    async def test_allows_request_when_under_limit(self, mock_app, mock_redis, mock_request, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis, max_requests=100)
        mock_redis.incr.return_value = 1

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200
        mock_redis.incr.assert_awaited_once_with("ratelimit:192.168.1.100:/api/v1/agents")
        mock_redis.expire.assert_awaited_once_with("ratelimit:192.168.1.100:/api/v1/agents", 60)

    async def test_allows_request_at_limit(self, mock_app, mock_redis, mock_request, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis, max_requests=100)
        mock_redis.incr.return_value = 100

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200

    async def test_blocks_request_over_limit(self, mock_app, mock_redis, mock_request, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis, max_requests=100)
        mock_redis.incr.return_value = 101

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Too many requests" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "60"

    async def test_skips_rate_limiting_for_health(self, mock_app, mock_redis, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis)
        health_request = MagicMock(spec=Request)
        health_request.url.path = "/health"

        response = await middleware.dispatch(health_request, mock_call_next)

        assert response.status_code == 200
        mock_redis.incr.assert_not_awaited()

    async def test_skips_rate_limiting_when_no_redis(self, mock_app, mock_request, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=None)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200

    async def test_handles_redis_failure_gracefully(self, mock_app, mock_redis, mock_request, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis)
        mock_redis.incr.side_effect = Exception("Redis connection failed")

        # Should not raise, just pass through
        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200

    async def test_handles_unknown_client_ip(self, mock_app, mock_redis, mock_call_next):
        middleware = RateLimitMiddleware(mock_app, redis=mock_redis, max_requests=100)
        mock_redis.incr.return_value = 1
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/agents"
        request.client = None

        response = await middleware.dispatch(request, mock_call_next)

        assert response.status_code == 200
        mock_redis.incr.assert_awaited_once_with("ratelimit:unknown:/api/v1/agents")
