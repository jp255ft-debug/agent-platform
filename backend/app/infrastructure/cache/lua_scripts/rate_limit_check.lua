-- rate_limit_check.lua
-- Token bucket rate limiter with automatic refill.
--
-- KEYS[1] = rate_limit:{agent_id}:{resource_type}
-- ARGV[1] = max_tokens (integer string)
-- ARGV[2] = refill_rate (tokens per second, integer string)
-- ARGV[3] = current_timestamp (unix seconds, integer string)
-- ARGV[4] = cost (tokens to consume, integer string, default: 1)
--
-- Returns:
--   1 if request is allowed (tokens consumed)
--   0 if rate limited (no tokens available)
--   TTL of the key in seconds (for informational purposes)

local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4] or 1)

-- Get current state
local state = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(state[1])
local last_refill = tonumber(state[2])

if not tokens then
    -- First request: initialize with full tokens
    tokens = max_tokens
    last_refill = now
end

-- Calculate refill
local elapsed = now - last_refill
local refill = math.floor(elapsed * refill_rate)
if refill > 0 then
    tokens = math.min(max_tokens, tokens + refill)
    last_refill = now
end

-- Check if enough tokens
if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    -- Set TTL to expire unused rate limiters (refill all tokens = idle)
    local idle_ttl = math.ceil(max_tokens / refill_rate) + 1
    redis.call('EXPIRE', key, idle_ttl)
    return 1
else
    -- Update last_refill for accurate next check
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    return 0
end
