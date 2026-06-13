# ADR-003: Event Sourcing with PostgreSQL

## Status
Proposed

## Context
Need audit trail and state reconstruction.

## Decision
Use PostgreSQL as event store with JSONB.

## Consequences
- Full audit trail
- Temporal queries
- Snapshot support
