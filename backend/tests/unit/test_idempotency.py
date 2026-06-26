"""Unit tests for IdempotencyService."""
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis


class TestIdempotencyService:
    """Tests for IdempotencyService."""

    def test_init(self, mock_redis):
        """Test initialization stores redis client."""
        from app.application.services.idempotency import IdempotencyService

        service = IdempotencyService(mock_redis)
        assert service._redis == mock_redis
        assert service._ttl == 3600

    async def test_is_processed_returns_false(self, mock_redis):
        """Test is_processed returns False when key doesn't exist."""
        from app.application.services.idempotency import IdempotencyService

        mock_redis.exists = AsyncMock(return_value=False)
        service = IdempotencyService(mock_redis)

        result = await service.is_processed("key-123")
        assert result is False
        mock_redis.exists.assert_awaited_once_with("idempotency:key-123")

    async def test_is_processed_returns_true(self, mock_redis):
        """Test is_processed returns True when key exists."""
        from app.application.services.idempotency import IdempotencyService

        mock_redis.exists = AsyncMock(return_value=True)
        service = IdempotencyService(mock_redis)

        result = await service.is_processed("key-123")
        assert result is True

    async def test_mark_processed(self, mock_redis):
        """Test mark_processed sets key with TTL."""
        from app.application.services.idempotency import IdempotencyService

        service = IdempotencyService(mock_redis)

        await service.mark_processed("key-123")
        mock_redis.setex.assert_awaited_once_with(
            "idempotency:key-123", 3600, "1"
        )

    async def test_get_result_returns_none(self, mock_redis):
        """Test get_result returns None when no cached result."""
        from app.application.services.idempotency import IdempotencyService

        mock_redis.get = AsyncMock(return_value=None)
        service = IdempotencyService(mock_redis)

        result = await service.get_result("key-123")
        assert result is None
        mock_redis.get.assert_awaited_once_with("idempotency:result:key-123")

    async def test_get_result_returns_value(self, mock_redis):
        """Test get_result returns cached result."""
        from app.application.services.idempotency import IdempotencyService

        mock_redis.get = AsyncMock(return_value="cached_response")
        service = IdempotencyService(mock_redis)

        result = await service.get_result("key-123")
        assert result == "cached_response"
