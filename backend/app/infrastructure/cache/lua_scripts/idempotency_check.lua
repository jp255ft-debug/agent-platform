-- idempotency_check.lua
-- Atomically checks and sets an idempotency key for consumption requests.
--
-- KEYS[1] = idempotency:{idempotency_key}
-- ARGV[1] = session_id (string) - the billing session ID to associate
-- ARGV[2] = ttl_seconds (integer string) - how long to keep the key
--
-- Returns:
--   nil (nil bulk reply) if this is a new request (first time seeing this key)
--   The existing session_id string if this is a retry (key already exists)

local existing = redis.call('GET', KEYS[1])
if existing then
    return existing
end

-- Set the key with the session_id and TTL
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return nil
