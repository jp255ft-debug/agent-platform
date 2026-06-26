"""Initialize Redis with default configuration."""
import asyncio

from app.core.config import settings
from redis.asyncio import Redis


async def init_redis() -> None:
    """Initialize Redis with default keys and configuration."""
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    # Set default rate limits
    await redis.set("config:rate_limit:default:max_tokens", 100)
    await redis.set("config:rate_limit:default:refill_rate", 10)

    # Set default TTLs
    await redis.set("config:cache:default_ttl", 300)
    await redis.set("config:idempotency:ttl", 3600)

    # Health check
    await redis.ping()
    print("Redis initialized successfully.")
    await redis.close()


if __name__ == "__main__":
    asyncio.run(init_redis())
