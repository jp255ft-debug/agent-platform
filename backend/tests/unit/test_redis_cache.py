"""Unit tests for RedisCache."""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.infrastructure.cache.redis_cache import RedisCache


@pytest.fixture
def mock_redis():
    """Create a mock Redis async client."""
    redis = MagicMock()
    redis.get = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.exists = AsyncMock()
    redis.incrby = AsyncMock()
    redis.expire = AsyncMock()
    return redis


@pytest.fixture
def cache(mock_redis):
    """Create a RedisCache with mocked Redis client."""
    return RedisCache(mock_redis, prefix="test")


class TestRedisCacheInitialization:
    """Test RedisCache initialization."""

    def test_default_prefix(self, mock_redis):
        cache = RedisCache(mock_redis)
        assert cache._prefix == "cache"

    def test_custom_prefix(self, mock_redis):
        cache = RedisCache(mock_redis, prefix="custom")
        assert cache._prefix == "custom"

    def test_key_formatting(self, mock_redis):
        cache = RedisCache(mock_redis, prefix="test")
        assert cache._key("foo") == "test:foo"
        assert cache._key("bar:baz") == "test:bar:baz"


class TestRedisCacheGet:
    """Test get method."""

    async def test_get_existing_key(self, cache, mock_redis):
        mock_redis.get.return_value = json.dumps({"hello": "world"})
        result = await cache.get("mykey")
        assert result == {"hello": "world"}
        mock_redis.get.assert_awaited_once_with("test:mykey")

    async def test_get_string_value(self, cache, mock_redis):
        mock_redis.get.return_value = json.dumps("simple_string")
        result = await cache.get("strkey")
        assert result == "simple_string"

    async def test_get_numeric_value(self, cache, mock_redis):
        mock_redis.get.return_value = json.dumps(42)
        result = await cache.get("numkey")
        assert result == 42

    async def test_get_list_value(self, cache, mock_redis):
        mock_redis.get.return_value = json.dumps([1, 2, 3])
        result = await cache.get("listkey")
        assert result == [1, 2, 3]

    async def test_get_nonexistent_key(self, cache, mock_redis):
        mock_redis.get.return_value = None
        result = await cache.get("missing")
        assert result is None

    async def test_get_empty_string(self, cache, mock_redis):
        mock_redis.get.return_value = json.dumps("")
        result = await cache.get("empty")
        assert result == ""


class TestRedisCacheSet:
    """Test set method."""

    async def test_set_with_default_ttl(self, cache, mock_redis):
        await cache.set("mykey", {"data": 123})
        mock_redis.setex.assert_awaited_once_with(
            "test:mykey", 300, json.dumps({"data": 123})
        )

    async def test_set_with_custom_ttl(self, cache, mock_redis):
        await cache.set("mykey", "value", ttl=60)
        mock_redis.setex.assert_awaited_once_with(
            "test:mykey", 60, json.dumps("value")
        )

    async def test_set_none_value(self, cache, mock_redis):
        await cache.set("nullkey", None)
        mock_redis.setex.assert_awaited_once_with(
            "test:nullkey", 300, json.dumps(None)
        )

    async def test_set_overwrites_existing(self, cache, mock_redis):
        await cache.set("mykey", "new_value")
        await cache.set("mykey", "updated_value")
        assert mock_redis.setex.await_count == 2


class TestRedisCacheDelete:
    """Test delete method."""

    async def test_delete_existing_key(self, cache, mock_redis):
        mock_redis.delete.return_value = 1
        result = await cache.delete("mykey")
        assert result is None
        mock_redis.delete.assert_awaited_once_with("test:mykey")

    async def test_delete_nonexistent_key(self, cache, mock_redis):
        mock_redis.delete.return_value = 0
        result = await cache.delete("missing")
        assert result is None


class TestRedisCacheExists:
    """Test exists method."""

    async def test_exists_returns_true(self, cache, mock_redis):
        mock_redis.exists.return_value = 1
        result = await cache.exists("mykey")
        assert result == 1

    async def test_exists_returns_false(self, cache, mock_redis):
        mock_redis.exists.return_value = 0
        result = await cache.exists("missing")
        assert result == 0


class TestRedisCacheIncrement:
    """Test increment method."""

    async def test_increment_default_amount(self, cache, mock_redis):
        mock_redis.incrby.return_value = 1
        result = await cache.increment("counter")
        assert result == 1
        mock_redis.incrby.assert_awaited_once_with("test:counter", 1)

    async def test_increment_custom_amount(self, cache, mock_redis):
        mock_redis.incrby.return_value = 10
        result = await cache.increment("counter", amount=5)
        assert result == 10
        mock_redis.incrby.assert_awaited_once_with("test:counter", 5)

    async def test_increment_negative_amount(self, cache, mock_redis):
        mock_redis.incrby.return_value = -5
        result = await cache.increment("counter", amount=-10)
        assert result == -5
        mock_redis.incrby.assert_awaited_once_with("test:counter", -10)


class TestRedisCacheExpire:
    """Test expire method."""

    async def test_expire_sets_ttl(self, cache, mock_redis):
        await cache.expire("mykey", 120)
        mock_redis.expire.assert_awaited_once_with("test:mykey", 120)

    async def test_expire_zero_ttl(self, cache, mock_redis):
        await cache.expire("mykey", 0)
        mock_redis.expire.assert_awaited_once_with("test:mykey", 0)
