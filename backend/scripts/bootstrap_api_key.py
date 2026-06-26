#!/usr/bin/env python3
"""Bootstrap script: creates the first API key for an agent.

Usage:
    docker compose exec backend python scripts/bootstrap_api_key.py <agent_id> [expires_in_days]

Example:
    docker compose exec backend python scripts/bootstrap_api_key.py agent_df70fd7b 365

Output:
    Prints the plain API key in format: key_id.plain_key
    Use this as the X-API-Key header for subsequent requests.
"""
import asyncio
import secrets
import sys
from datetime import datetime, timedelta, timezone

# Ensure we can import from app
sys.path.insert(0, "/app")

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.domain.aggregates.api_key import APIKeyAggregate
from app.infrastructure.db.repositories.event_store import PostgresEventStore


def hash_api_key(plain_key: str) -> str:
    """Hash an API key using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_key.encode("utf-8"), salt).decode("utf-8")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/bootstrap_api_key.py <agent_id> [expires_in_days]")
        sys.exit(1)

    agent_id = sys.argv[1]
    expires_in_days = int(sys.argv[2]) if len(sys.argv) > 2 else 365

    # Generate key pair
    key_id = f"key_{secrets.token_hex(8)}"
    plain_key = secrets.token_urlsafe(32)
    hashed_key = hash_api_key(plain_key)

    # Create engine and session
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 1. Create aggregate and generate events
            aggregate = APIKeyAggregate(agent_id=agent_id)
            aggregate.create(
                key_id=key_id,
                key_hash=hashed_key,
                expires_in_days=expires_in_days,
            )

            # 2. Persist events to event store
            event_store = PostgresEventStore(session)
            changes = aggregate.get_changes()
            await event_store.append_events(
                stream_id=f"api_key-{agent_id}",
                events=changes,
                expected_version=0,
            )

            # 3. Insert into SQL lookup table
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            created_at = datetime.now(timezone.utc)
            await session.execute(
                text("""
                    INSERT INTO api_keys (key_id, agent_id, key_hash, expires_at, created_at)
                    VALUES (:key_id, :agent_id, :key_hash, :expires_at, :created_at)
                    ON CONFLICT (key_id) DO NOTHING
                """),
                {
                    "key_id": key_id,
                    "agent_id": agent_id,
                    "key_hash": hashed_key,
                    "expires_at": expires_at,
                    "created_at": created_at,
                },
            )


            await session.commit()

            # 4. Output the key
            full_key = f"{key_id}.{plain_key}"
            print(f"✅ API Key created for agent: {agent_id}")
            print(f"   Key ID:     {key_id}")
            print(f"   Expires in: {expires_in_days} days")
            print(f"   Expires at: {expires_at}")
            print()
            print(f"   🔑 X-API-Key: {full_key}")
            print()
            print("   Use this in the header: X-API-Key: " + full_key)

        except Exception as e:
            await session.rollback()
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
