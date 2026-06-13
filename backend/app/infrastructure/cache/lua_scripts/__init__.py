"""Lua scripts for atomic Redis operations.

This package contains Lua scripts that are loaded into Redis
for atomic operations used by the Agent Platform:

- reserve_quota.lua: Atomic quota reservation for resource consumption
- rate_limit_check.lua: Token bucket rate limiter with auto-refill
- idempotency_check.lua: Idempotency key check-and-set
"""
