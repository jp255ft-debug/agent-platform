"""Repository for API key aggregates with Redis cache."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.aggregates.api_key import APIKeyAggregate
from app.infrastructure.db.repositories.event_store import PostgresEventStore


class APIKeyRepository:
    """Handles loading and saving APIKeyAggregate using event store + SQL lookup table."""

    def __init__(self, db: AsyncSession, redis: Optional[Redis] = None):
        self._event_store = PostgresEventStore(db)
        self._db = db
        self._redis = redis

    async def load_agent_keys(self, agent_id: str) -> APIKeyAggregate:
        """Load full aggregate from event store."""
        events = await self._event_store.load_stream(f"api_key-{agent_id}")
        if not events:
            return APIKeyAggregate(agent_id=agent_id)

        aggregate = APIKeyAggregate(agent_id=agent_id)
        for event in events:
            aggregate._apply(event)
        return aggregate

    async def save(self, aggregate: APIKeyAggregate) -> None:
        """Append pending events to event store and update SQL lookup table."""
        stream_id = f"api_key-{aggregate.agent_id}"
        changes = aggregate.get_changes()
        if not changes:
            return

        await self._event_store.append_events(
            stream_id=stream_id,
            events=changes,
            expected_version=aggregate.version - len(changes),
        )

        # Update SQL lookup table for fast key_id → (agent_id, key_hash) resolution
        for event in changes:
            if event.event_type() == "APIKeyCreated":
                # Convert ISO strings to datetime objects for PostgreSQL
                expires_at = event.data["expires_at"]
                created_at = event.data["created_at"]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)

                await self._db.execute(
                    text("""
                        INSERT INTO api_keys (key_id, agent_id, key_hash, expires_at, created_at)
                        VALUES (:key_id, :agent_id, :key_hash, :expires_at, :created_at)
                        ON CONFLICT (key_id) DO UPDATE SET
                            agent_id = EXCLUDED.agent_id,
                            key_hash = EXCLUDED.key_hash,
                            expires_at = EXCLUDED.expires_at
                    """),
                    {
                        "key_id": event.data["key_id"],
                        "agent_id": aggregate.agent_id,
                        "key_hash": event.data["key_hash"],
                        "expires_at": expires_at,
                        "created_at": created_at,
                    },
                )
                # Invalidate Redis cache
                if self._redis:
                    await self._redis.delete(f"api_key:{event.data['key_id']}")

            elif event.event_type() == "APIKeyRevoked":
                await self._db.execute(
                    text("UPDATE api_keys SET revoked = TRUE WHERE key_id = :key_id"),
                    {"key_id": event.data["key_id"]},
                )
                if self._redis:
                    await self._redis.delete(f"api_key:{event.data['key_id']}")

            elif event.event_type() == "APIKeyExpired":
                await self._db.execute(
                    text("UPDATE api_keys SET revoked = TRUE WHERE key_id = :key_id"),
                    {"key_id": event.data["key_id"]},
                )
                if self._redis:
                    await self._redis.delete(f"api_key:{event.data['key_id']}")

    async def get_key_hash(self, key_id: str) -> tuple[Optional[str], Optional[str]]:
        """Retrieve (agent_id, key_hash) for a given key_id.

        Uses Redis cache for fast lookup, falls back to SQL table.
        """
        # 1. Try Redis cache first
        if self._redis:
            cached = await self._redis.get(f"api_key:{key_id}")
            if cached:
                data = json.loads(cached)
                return data["agent_id"], data["key_hash"]

        # 2. Query SQL lookup table
        result = await self._db.execute(
            text("""
                SELECT agent_id, key_hash
                FROM api_keys
                WHERE key_id = :key_id AND NOT revoked
            """),
            {"key_id": key_id},
        )
        row = result.fetchone()
        if not row:
            return None, None

        agent_id, key_hash = row[0], row[1]

        # 3. Cache in Redis for 5 minutes
        if self._redis:
            await self._redis.setex(
                f"api_key:{key_id}",
                300,
                json.dumps({"agent_id": agent_id, "key_hash": key_hash}),
            )

        return agent_id, key_hash
