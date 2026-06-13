# ADR-004: Rate Limiting with Redis

## Status
Proposed

## Context
Need to prevent resource abuse.

## Decision
Use Redis with Token Bucket algorithm.

## Consequences
- Sub-millisecond latency
- Distributed rate limiting
- Burst handling
