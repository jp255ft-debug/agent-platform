from redis.asyncio import Redis


class IdempotencyService:
    def __init__(self, redis: Redis):
        self._redis = redis
        self._ttl = 3600

    async def is_processed(self, idempotency_key: str) -> bool:
        return await self._redis.exists(f"idempotency:{idempotency_key}")

    async def mark_processed(self, idempotency_key: str) -> None:
        await self._redis.setex(f"idempotency:{idempotency_key}", self._ttl, "1")

    async def get_result(self, idempotency_key: str) -> str | None:
        return await self._redis.get(f"idempotency:result:{idempotency_key}")
