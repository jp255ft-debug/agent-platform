"""PostgreSQL event store implementation."""
import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConcurrencyError
from app.domain.events.base import DomainEvent
from app.domain.repositories.event_store import EventStore
from app.infrastructure.db.upcasters import EventUpcaster


class PostgresEventStore(EventStore):
    """Event store backed by PostgreSQL using JSONB."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def append_events(
        self, stream_id: str, events: list[DomainEvent],
        expected_version: int | None = None,
    ) -> None:
        """Append events to a stream with optimistic concurrency control.

        Uses a UNIQUE(stream_id, version) constraint at the database level
        to detect concurrent writes. If violated, raises ConcurrencyError
        so the application layer can retry.
        """
        try:
            for i, event in enumerate(events):
                event_dict = event.to_dict()
                event_dict["stream_id"] = stream_id
                event_dict["version"] = (expected_version or 0) + i + 1

                query = text("""
                    INSERT INTO events (event_id, stream_id, version, event_type,
                        aggregate_id, data, occurred_at)
                    VALUES (:event_id, :stream_id, :version, :event_type,
                        :aggregate_id, :data, :occurred_at)
                """)
                await self._session.execute(query, {
                    "event_id": event_dict["event_id"],
                    "stream_id": stream_id,
                    "version": event_dict["version"],
                    "event_type": event_dict["event_type"],
                    "aggregate_id": event_dict["aggregate_id"],
                    "data": json.dumps(event_dict["data"]),
                    "occurred_at": event.occurred_at,
                })
        except IntegrityError as e:
            if "uq_stream_version" in str(e.orig):
                # Load actual version to provide meaningful error context
                actual = await self._get_latest_version(stream_id)
                raise ConcurrencyError(
                    aggregate_id=stream_id,
                    expected_version=expected_version or 0,
                    actual_version=actual,
                ) from e
            raise

    async def _get_latest_version(self, stream_id: str) -> int:
        """Get the latest version for a stream (used for OCC error context)."""
        query = text("""
            SELECT COALESCE(MAX(version), 0)
            FROM events
            WHERE stream_id = :stream_id
        """)
        result = await self._session.execute(query, {"stream_id": stream_id})
        return result.scalar() or 0

    async def load_stream(self, stream_id: str) -> list[DomainEvent]:
        """Load all events for a stream in order."""
        query = text("""
            SELECT event_id, stream_id, version, event_type,
                aggregate_id, data, occurred_at
            FROM events
            WHERE stream_id = :stream_id
            ORDER BY version ASC
        """)
        result = await self._session.execute(query, {"stream_id": stream_id})
        rows = result.fetchall()
        return [self._row_to_event(row) for row in rows]

    async def load_stream_from_version(
        self, stream_id: str, from_version: int,
    ) -> list[DomainEvent]:
        """Load events from a specific version onwards."""
        query = text("""
            SELECT event_id, stream_id, version, event_type,
                aggregate_id, data, occurred_at
            FROM events
            WHERE stream_id = :stream_id AND version >= :from_version
            ORDER BY version ASC
        """)
        result = await self._session.execute(query, {
            "stream_id": stream_id,
            "from_version": from_version,
        })
        rows = result.fetchall()
        return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row) -> DomainEvent:
        """Convert a database row back to a DomainEvent.

        Before deserialization, the raw payload passes through the
        EventUpcaster pipeline. This ensures legacy V1 events are
        transparently upgraded to the latest schema version without
        requiring a backfill migration on the database.
        """
        from app.domain.events.agent_events import (
            AgentDelegated,
            AgentDelegationRevoked,
            AgentRegistered,
            AgentReputationUpdated,
        )
        from app.domain.events.api_key_events import (
            APIKeyCreated,
            APIKeyExpired,
            APIKeyRevoked,
            APIKeyRotated,
            APIKeyUsed,
        )
        from app.domain.events.billing_events import (
            BillingSessionClosed,
            BillingSessionSettled,
            BillingSessionStarted,
            ResourceConsumed,
            ResourceConsumedV2,
        )
        from app.domain.events.gpu_events import (
            GPULeaseActivated,
            GPULeaseExpired,
            GPULeaseExtended,
            GPULeaseProvisioned,
            GPULeaseRequested,
            GPULeaseTerminated,
        )
        from app.domain.events.payment_events import (
            InvoiceGenerated,
            InvoicePaid,
            PaymentFailed,
            PaymentReceived,
            PaymentVerified,
        )

        event_type_map = {
            # Agent events
            "AgentRegistered": AgentRegistered,
            "AgentDelegated": AgentDelegated,
            "AgentDelegationRevoked": AgentDelegationRevoked,
            "AgentReputationUpdated": AgentReputationUpdated,
            # Billing events
            "BillingSessionStarted": BillingSessionStarted,
            "ResourceConsumed": ResourceConsumed,
            "ResourceConsumedV2": ResourceConsumedV2,
            "BillingSessionClosed": BillingSessionClosed,
            "BillingSessionSettled": BillingSessionSettled,
            # Payment events
            "PaymentReceived": PaymentReceived,
            "PaymentVerified": PaymentVerified,
            "PaymentFailed": PaymentFailed,
            "InvoiceGenerated": InvoiceGenerated,
            "InvoicePaid": InvoicePaid,
            # API Key events
            "APIKeyCreated": APIKeyCreated,
            "APIKeyRevoked": APIKeyRevoked,
            "APIKeyExpired": APIKeyExpired,
            "APIKeyRotated": APIKeyRotated,
            "APIKeyUsed": APIKeyUsed,
            # GPU Lease events
            "GPULeaseRequested": GPULeaseRequested,
            "GPULeaseProvisioned": GPULeaseProvisioned,
            "GPULeaseActivated": GPULeaseActivated,
            "GPULeaseExtended": GPULeaseExtended,
            "GPULeaseTerminated": GPULeaseTerminated,
            "GPULeaseExpired": GPULeaseExpired,
        }

        # ── Step 1: Parse raw JSONB data ──────────────────────────
        data = json.loads(row.data) if isinstance(row.data, str) else row.data

        # ── Step 2: Build raw payload for upcaster ─────────────────
        raw_payload = {
            "event_id": row.event_id,
            "stream_id": row.stream_id,
            "version": row.version,
            "event_type": row.event_type,
            "aggregate_id": row.aggregate_id,
            "data": data,
            "occurred_at": row.occurred_at.isoformat() if isinstance(row.occurred_at, datetime) else row.occurred_at,
        }

        # ── Step 3: Apply upcast transformations ───────────────────
        upcasted = EventUpcaster.upcast(raw_payload)

        # ── Step 4: Deserialize to domain event ────────────────────
        event_cls = event_type_map.get(upcasted["event_type"])
        if event_cls is None:
            raise ValueError(f"Unknown event type after upcast: {upcasted['event_type']}")

        event: DomainEvent = event_cls.__new__(event_cls)  # type: ignore[call-overload]
        event.event_id = upcasted["event_id"]
        event.aggregate_id = upcasted["aggregate_id"]
        event.occurred_at = (
            row.occurred_at
            if isinstance(row.occurred_at, datetime)
            else datetime.fromisoformat(upcasted["occurred_at"])
        )
        event.data = upcasted["data"]
        return event
