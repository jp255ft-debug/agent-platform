"""Redis Lua script client for atomic operations.

This module provides a client that loads and executes Lua scripts
on Redis for atomic operations like quota reservation, rate limiting,
and idempotency checks.

Usage:
    from app.infrastructure.cache.redis_lua_client import RedisLuaClient

    lua_client = RedisLuaClient(redis_client)
    result = await lua_client.reserve_quota("agent_123", "llm", 100, 3600)
"""

import logging
from pathlib import Path
from typing import Any, Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Path to Lua scripts directory
LUA_SCRIPTS_DIR = Path(__file__).parent / "lua_scripts"


class RedisLuaClient:
    """Client for executing Redis Lua scripts.

    Loads Lua scripts by SHA for efficient execution and provides
    typed Python methods for each operation.
    """

    def __init__(self, redis: Redis):
        self._redis = redis
        self._scripts: dict[str, str] = {}  # name -> SHA

    async def load_scripts(self) -> None:
        """Load all Lua scripts into Redis and cache their SHAs."""
        script_files = {
            "reserve_quota": LUA_SCRIPTS_DIR / "reserve_quota.lua",
            "rate_limit_check": LUA_SCRIPTS_DIR / "rate_limit_check.lua",
            "idempotency_check": LUA_SCRIPTS_DIR / "idempotency_check.lua",
        }

        for name, path in script_files.items():
            if not path.exists():
                logger.warning(f"Lua script not found: {path}")
                continue

            script = path.read_text(encoding="utf-8")
            sha = await self._redis.script_load(script)
            self._scripts[name] = sha
            logger.info(f"Loaded Lua script '{name}' (SHA: {sha[:16]}...)")

    async def reserve_quota(
        self, agent_id: str, resource_type: str, amount: int, ttl: int = 3600
    ) -> int:
        """Atomically reserve quota for a resource consumption.

        Args:
            agent_id: The agent's identifier
            resource_type: Type of resource (llm, stt, tts, etc.)
            amount: Amount of quota to reserve
            ttl: TTL in seconds for the quota key

        Returns:
            1 if quota was successfully reserved
            0 if insufficient quota
            -1 if no quota is configured (key doesn't exist)
        """
        sha = self._scripts.get("reserve_quota")
        if not sha:
            raise RuntimeError("reserve_quota script not loaded")

        key = f"quota:{agent_id}:{resource_type}"
        result: Any = await self._redis.evalsha(sha, 1, [key], [str(amount)], [str(ttl)])  # type: ignore[misc]
        return int(result) if result is not None else 0

    async def check_rate_limit(
        self,
        agent_id: str,
        resource_type: str,
        max_tokens: int,
        refill_rate: int,
        cost: int = 1,
    ) -> bool:
        """Check if a request is within rate limits using token bucket.

        Args:
            agent_id: The agent's identifier
            resource_type: Type of resource
            max_tokens: Maximum tokens in the bucket
            refill_rate: Tokens refilled per second
            cost: Number of tokens to consume (default: 1)

        Returns:
            True if request is allowed, False if rate limited
        """
        sha = self._scripts.get("rate_limit_check")
        if not sha:
            raise RuntimeError("rate_limit_check script not loaded")

        import time

        key = f"rate_limit:{agent_id}:{resource_type}"
        now = int(time.time())
        result: Any = await self._redis.evalsha(  # type: ignore[misc]
            sha, 1, [key], [str(max_tokens)], [str(refill_rate)], [str(now)], [str(cost)]
        )
        return result == 1

    async def check_idempotency(
        self, idempotency_key: str, session_id: str, ttl: int = 86400
    ) -> Optional[str]:
        """Atomically check and set an idempotency key.

        Args:
            idempotency_key: The idempotency key from the request
            session_id: The billing session ID to associate
            ttl: TTL in seconds (default: 24 hours)

        Returns:
            None if this is a new request (key was set)
            Existing session_id string if this is a retry
        """
        sha = self._scripts.get("idempotency_check")
        if not sha:
            raise RuntimeError("idempotency_check script not loaded")

        key = f"idempotency:{idempotency_key}"
        result: Any = await self._redis.evalsha(sha, 1, [key], [session_id], [str(ttl)])  # type: ignore[misc]
        if result is not None:
            return result.decode("utf-8") if isinstance(result, bytes) else result
        return None

    async def get_quota_remaining(
        self, agent_id: str, resource_type: str
    ) -> Optional[int]:
        """Get remaining quota for an agent and resource type.

        Args:
            agent_id: The agent's identifier
            resource_type: Type of resource

        Returns:
            Remaining quota amount, or None if no quota is configured
        """
        key = f"quota:{agent_id}:{resource_type}"
        value = await self._redis.get(key)
        if value is not None:
            return int(value)
        return None

    async def set_quota(
        self, agent_id: str, resource_type: str, amount: int, ttl: int = 3600
    ) -> None:
        """Set the quota for an agent and resource type.

        Args:
            agent_id: The agent's identifier
            resource_type: Type of resource
            amount: Total quota amount
            ttl: TTL in seconds
        """
        key = f"quota:{agent_id}:{resource_type}"
        await self._redis.set(key, str(amount), ex=ttl)
