"""Unit tests for RedisLuaClient."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.cache.redis_lua_client import RedisLuaClient


@pytest.fixture
def mock_redis():
    """Create a mock Redis async client."""
    redis = MagicMock()
    redis.script_load = AsyncMock()
    redis.evalsha = AsyncMock()
    redis.get = AsyncMock()
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def lua_client(mock_redis):
    """Create a RedisLuaClient with mocked Redis client."""
    return RedisLuaClient(mock_redis)


class TestLoadScripts:
    """Test load_scripts method."""

    async def test_load_all_scripts_success(self, lua_client, mock_redis):
        """Should load all three Lua scripts successfully."""
        mock_redis.script_load.side_effect = ["sha1", "sha2", "sha3"]

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="-- lua script"),
        ):
            await lua_client.load_scripts()

        assert lua_client._scripts["reserve_quota"] == "sha1"
        assert lua_client._scripts["rate_limit_check"] == "sha2"
        assert lua_client._scripts["idempotency_check"] == "sha3"
        assert mock_redis.script_load.await_count == 3

    async def test_load_scripts_skips_missing_file(self, lua_client, mock_redis):
        """Should skip scripts whose files don't exist."""
        mock_redis.script_load.side_effect = ["sha1", "sha3"]

        with patch("pathlib.Path.exists", side_effect=[True, False, True]):
            with patch("pathlib.Path.read_text", return_value="-- lua"):
                await lua_client.load_scripts()

        assert "reserve_quota" in lua_client._scripts
        assert "rate_limit_check" not in lua_client._scripts
        assert "idempotency_check" in lua_client._scripts
        assert mock_redis.script_load.await_count == 2


class TestReserveQuota:
    """Test reserve_quota method."""

    async def test_reserve_quota_success(self, lua_client, mock_redis):
        lua_client._scripts["reserve_quota"] = "sha_reserve"
        mock_redis.evalsha.return_value = 1

        result = await lua_client.reserve_quota("agent_123", "llm", 100, 3600)

        assert result == 1
        mock_redis.evalsha.assert_awaited_once_with(
            "sha_reserve", 1, "quota:agent_123:llm", "100", "3600"
        )

    async def test_reserve_quota_insufficient(self, lua_client, mock_redis):
        lua_client._scripts["reserve_quota"] = "sha_reserve"
        mock_redis.evalsha.return_value = 0

        result = await lua_client.reserve_quota("agent_123", "llm", 1000, 3600)
        assert result == 0

    async def test_reserve_quota_no_quota_configured(self, lua_client, mock_redis):
        lua_client._scripts["reserve_quota"] = "sha_reserve"
        mock_redis.evalsha.return_value = -1

        result = await lua_client.reserve_quota("agent_456", "stt", 50, 1800)
        assert result == -1

    async def test_reserve_quota_script_not_loaded(self, lua_client, mock_redis):
        with pytest.raises(RuntimeError, match="reserve_quota script not loaded"):
            await lua_client.reserve_quota("agent_123", "llm", 100, 3600)


class TestCheckRateLimit:
    """Test check_rate_limit method."""

    async def test_rate_limit_allowed(self, lua_client, mock_redis):
        lua_client._scripts["rate_limit_check"] = "sha_rate"
        mock_redis.evalsha.return_value = 1

        result = await lua_client.check_rate_limit(
            "agent_123", "llm", max_tokens=100, refill_rate=10, cost=1
        )

        assert result is True
        # Verify evalsha was called with correct args (key + 4 args)
        call_args = mock_redis.evalsha.await_args
        assert call_args[0][0] == "sha_rate"
        assert call_args[0][1] == 1
        assert call_args[0][2] == "rate_limit:agent_123:llm"

    async def test_rate_limit_denied(self, lua_client, mock_redis):
        lua_client._scripts["rate_limit_check"] = "sha_rate"
        mock_redis.evalsha.return_value = 0

        result = await lua_client.check_rate_limit(
            "agent_123", "llm", max_tokens=0, refill_rate=1, cost=1
        )
        assert result is False

    async def test_rate_limit_script_not_loaded(self, lua_client, mock_redis):
        with pytest.raises(RuntimeError, match="rate_limit_check script not loaded"):
            await lua_client.check_rate_limit("agent_123", "llm", max_tokens=10, refill_rate=1)


class TestCheckIdempotency:
    """Test check_idempotency method."""

    async def test_idempotency_new_request(self, lua_client, mock_redis):
        lua_client._scripts["idempotency_check"] = "sha_idem"
        mock_redis.evalsha.return_value = None

        result = await lua_client.check_idempotency("key-123", "session-456", 86400)

        assert result is None
        mock_redis.evalsha.assert_awaited_once_with(
            "sha_idem", 1, "idempotency:key-123", "session-456", "86400"
        )

    async def test_idempotency_retry(self, lua_client, mock_redis):
        lua_client._scripts["idempotency_check"] = "sha_idem"
        mock_redis.evalsha.return_value = "session-456"

        result = await lua_client.check_idempotency("key-123", "session-456", 86400)

        assert result == "session-456"

    async def test_idempotency_retry_bytes_response(self, lua_client, mock_redis):
        """Should decode bytes response to string."""
        lua_client._scripts["idempotency_check"] = "sha_idem"
        mock_redis.evalsha.return_value = b"session-789"

        result = await lua_client.check_idempotency("key-abc", "session-789", 3600)

        assert result == "session-789"

    async def test_idempotency_script_not_loaded(self, lua_client, mock_redis):
        with pytest.raises(RuntimeError, match="idempotency_check script not loaded"):
            await lua_client.check_idempotency("key-123", "session-456", 86400)


class TestGetQuotaRemaining:
    """Test get_quota_remaining method."""

    async def test_get_quota_remaining_exists(self, lua_client, mock_redis):
        mock_redis.get.return_value = "500"

        result = await lua_client.get_quota_remaining("agent_123", "llm")

        assert result == 500
        mock_redis.get.assert_awaited_once_with("quota:agent_123:llm")

    async def test_get_quota_remaining_none(self, lua_client, mock_redis):
        mock_redis.get.return_value = None

        result = await lua_client.get_quota_remaining("agent_999", "tts")

        assert result is None

    async def test_get_quota_remaining_zero(self, lua_client, mock_redis):
        mock_redis.get.return_value = "0"

        result = await lua_client.get_quota_remaining("agent_123", "llm")

        assert result == 0


class TestSetQuota:
    """Test set_quota method."""

    async def test_set_quota_with_default_ttl(self, lua_client, mock_redis):
        await lua_client.set_quota("agent_123", "llm", 1000)

        mock_redis.set.assert_awaited_once_with(
            "quota:agent_123:llm", "1000", ex=3600
        )

    async def test_set_quota_with_custom_ttl(self, lua_client, mock_redis):
        await lua_client.set_quota("agent_123", "llm", 500, ttl=7200)

        mock_redis.set.assert_awaited_once_with(
            "quota:agent_123:llm", "500", ex=7200
        )

    async def test_set_quota_zero_amount(self, lua_client, mock_redis):
        await lua_client.set_quota("agent_123", "llm", 0)

        mock_redis.set.assert_awaited_once_with(
            "quota:agent_123:llm", "0", ex=3600
        )
