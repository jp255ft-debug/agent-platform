"""Unit tests for RateLimiter."""
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.hgetall = AsyncMock(return_value={"tokens": "50", "last_refill": "1000000"})
    redis.eval = AsyncMock(return_value=1)
    return redis


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_init(self, mock_redis):
        """Test initialization stores redis client."""
        from app.application.services.rate_limiter import RateLimiter

        limiter = RateLimiter(mock_redis)
        assert limiter._redis == mock_redis

    async def test_check_rate_limit_allowed(self, mock_redis):
        """Test check_rate_limit returns True when allowed."""
        from app.application.services.rate_limiter import RateLimiter

        mock_redis.eval = AsyncMock(return_value=1)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("agent-123", "compute")
        assert result == 1
        mock_redis.eval.assert_awaited_once()

    async def test_check_rate_limit_denied(self, mock_redis):
        """Test check_rate_limit returns False when denied."""
        from app.application.services.rate_limiter import RateLimiter

        mock_redis.eval = AsyncMock(return_value=0)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit("agent-123", "compute")
        assert result == 0

    async def test_check_rate_limit_custom_params(self, mock_redis):
        """Test check_rate_limit with custom max_tokens and refill_rate."""
        from app.application.services.rate_limiter import RateLimiter

        mock_redis.eval = AsyncMock(return_value=1)
        limiter = RateLimiter(mock_redis)

        result = await limiter.check_rate_limit(
            "agent-123", "compute", max_tokens=200, refill_rate=20.0
        )
        assert result == 1

    async def test_get_remaining_tokens(self, mock_redis):
        """Test get_remaining_tokens returns token count."""
        from app.application.services.rate_limiter import RateLimiter

        mock_redis.hgetall = AsyncMock(
            return_value={b"tokens": b"75", b"last_refill": b"1000000"}
        )
        limiter = RateLimiter(mock_redis)

        result = await limiter.get_remaining_tokens("agent-123", "compute")
        assert result == 75
        mock_redis.hgetall.assert_awaited_once_with(
            "rate_limit:agent-123:compute"
        )

    async def test_get_remaining_tokens_zero(self, mock_redis):
        """Test get_remaining_tokens returns 0 when no bucket exists."""
        from app.application.services.rate_limiter import RateLimiter

        mock_redis.hgetall = AsyncMock(return_value={})
        limiter = RateLimiter(mock_redis)

        result = await limiter.get_remaining_tokens("agent-123", "compute")
        assert result == 0

    def test_token_bucket_script_exists(self, mock_redis):
        """Test the token bucket Lua script is defined."""
        from app.application.services.rate_limiter import RateLimiter

        limiter = RateLimiter(mock_redis)
        assert hasattr(limiter, "_token_bucket_script")
        assert "local key = KEYS[1]" in limiter._token_bucket_script
        assert "max_tokens" in limiter._token_bucket_script
