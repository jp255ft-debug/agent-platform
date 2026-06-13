from redis.asyncio import Redis

class RateLimiter:
    def __init__(self, redis: Redis):
        self._redis = redis

    async def check_rate_limit(self, agent_id: str, resource_type: str,
        max_tokens: int = 100, refill_rate: float = 10.0) -> bool:
        key = f"rate_limit:{agent_id}:{resource_type}"
        return await self._redis.eval(self._token_bucket_script, 1, key, max_tokens, refill_rate)

    async def get_remaining_tokens(self, agent_id: str, resource_type: str) -> int:
        key = f"rate_limit:{agent_id}:{resource_type}"
        result = await self._redis.hgetall(key)
        return int(result.get("tokens", 0))

    _token_bucket_script = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = redis.call('TIME')[1]
local bucket = redis.call('HGETALL', key)
local tokens = max_tokens
local last_refill = now
if #bucket > 0 then
    tokens = tonumber(bucket[2])
    last_refill = tonumber(bucket[4])
    local elapsed = now - last_refill
    tokens = math.min(max_tokens, tokens + elapsed * refill_rate)
end
if tokens >= 1 then
    redis.call('HSET', key, 'tokens', tokens - 1, 'last_refill', now)
    redis.call('EXPIRE', key, 10)
    return 1
end
redis.call('HSET', key, 'tokens', 0, 'last_refill', now)
redis.call('EXPIRE', key, 10)
return 0
"""
