"""Redis cache implementation."""
import json
from typing import Any

from redis.asyncio import Redis


class RedisCache:
    """Generic Redis cache with JSON serialization."""

    def __init__(self, redis: Redis, prefix: str = "cache"):
        self._redis = redis
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        data = await self._redis.get(self._key(key))
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        await self._redis.setex(self._key(key), ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        return await self._redis.exists(self._key(key))

    async def increment(self, key: str, amount: int = 1) -> int:
        return await self._redis.incrby(self._key(key), amount)

    async def expire(self, key: str, ttl: int) -> None:
        await self._redis.expire(self._key(key), ttl)
