"""PostgreSQL snapshot repository implementation."""
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.snapshot_repo import SnapshotRepository


class PostgresSnapshotRepository(SnapshotRepository):
    """Snapshot repository backed by PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save_snapshot(
        self, aggregate_id: str, aggregate_type: str,
        data: dict, version: int,
    ) -> None:
        """Save a snapshot of an aggregate."""
        query = text("""
            INSERT INTO snapshots (aggregate_id, aggregate_type, data, version, created_at)
            VALUES (:aggregate_id, :aggregate_type, :data, :version, NOW())
            ON CONFLICT (aggregate_id) DO UPDATE SET
                aggregate_type = EXCLUDED.aggregate_type,
                data = EXCLUDED.data,
                version = EXCLUDED.version,
                created_at = NOW()
        """)
        await self._session.execute(query, {
            "aggregate_id": aggregate_id,
            "aggregate_type": aggregate_type,
            "data": json.dumps(data),
            "version": version,
        })

    async def load_snapshot(self, aggregate_id: str) -> dict | None:
        """Load the latest snapshot for an aggregate."""
        query = text("""
            SELECT data, version FROM snapshots
            WHERE aggregate_id = :aggregate_id
            ORDER BY version DESC LIMIT 1
        """)
        result = await self._session.execute(query, {"aggregate_id": aggregate_id})
        row = result.fetchone()
        if row:
            data = json.loads(row.data) if isinstance(row.data, str) else row.data
            return {"data": data, "version": row.version}
        return None

    async def delete_snapshots(self, aggregate_id: str) -> None:
        """Delete all snapshots for an aggregate."""
        query = text("DELETE FROM snapshots WHERE aggregate_id = :aggregate_id")
        await self._session.execute(query, {"aggregate_id": aggregate_id})
