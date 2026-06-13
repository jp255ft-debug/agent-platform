"""Initialize database schema."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings


INIT_SCHEMA_SQL = """
-- Event store table
CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY,
    stream_id VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(stream_id, version)
);

-- Snapshots table
CREATE TABLE IF NOT EXISTS snapshots (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    aggregate_type VARCHAR(100) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for event store
CREATE INDEX IF NOT EXISTS idx_events_stream_id ON events(stream_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_aggregate_id ON events(aggregate_id);
CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_data_gin ON events USING GIN (data);

-- Indexes for snapshots
CREATE INDEX IF NOT EXISTS idx_snapshots_aggregate_type ON snapshots(aggregate_type);

-- Idempotency table
CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key VARCHAR(255) PRIMARY KEY,
    response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Outbox table for reliable event publishing
CREATE TABLE IF NOT EXISTS outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbox_published ON outbox(published) WHERE published = FALSE;
"""


async def init_database() -> None:
    """Initialize the database schema."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        isolation_level="AUTOCOMMIT",
    )
    async with engine.connect() as conn:
        for statement in INIT_SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if statement:
                await conn.execute(statement)
    await engine.dispose()
    print("Database schema initialized successfully.")


if __name__ == "__main__":
    asyncio.run(init_database())
