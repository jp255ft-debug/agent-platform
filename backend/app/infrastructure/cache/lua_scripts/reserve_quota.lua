-- reserve_quota.lua
-- Atomically reserves quota for a resource consumption.
--
-- KEYS[1] = quota:{agent_id}:{resource_type}
-- ARGV[1] = amount_to_reserve (integer string)
-- ARGV[2] = ttl_seconds (integer string)
--
-- Returns:
--   1 if quota was successfully reserved
--   0 if insufficient quota
--  -1 if key doesn't exist (no quota configured)

local current = redis.call('GET', KEYS[1])
if not current then
    return -1
end

local current_num = tonumber(current)
local to_reserve = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

if current_num >= to_reserve then
    local remaining = current_num - to_reserve
    redis.call('SET', KEYS[1], remaining, 'EX', ttl)
    return 1
else
    return 0
end
