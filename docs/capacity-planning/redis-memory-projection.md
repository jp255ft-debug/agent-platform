# Redis Memory Projection

## Key Patterns
- rate_limit:{agent_id}:{resource_type} -> ~200 bytes per key
- session:{session_id} -> ~500 bytes per key
- idempotency:{idempotency_key} -> ~300 bytes per key

## Estimates
- 10,000 agents: ~50 MB
- 100,000 sessions/hour: ~500 MB
- TTL-based cleanup: automatic
