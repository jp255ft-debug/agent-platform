"""PostgreSQL event store implementation."""
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.events.base import DomainEvent
from app.domain.repositories.event_store import EventStore


class PostgresEventStore(EventStore):
    """Event store backed by PostgreSQL using JSONB."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def append_events(
        self, stream_id: str, events: List[DomainEvent],
        expected_version: Optional[int] = None,
    ) -> None:
        """Append events to a stream with optimistic concurrency control."""
        async with self._session.begin():
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
                    "occurred_at": event_dict["occurred_at"],
                })

    async def load_stream(self, stream_id: str) -> List[DomainEvent]:
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
    ) -> List[DomainEvent]:
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
        """Convert a database row back to a DomainEvent."""
        from app.domain.events.agent_events import (
            AgentRegistered, AgentDelegated, AgentDelegationRevoked, AgentReputationUpdated,
        )
        from app.domain.events.billing_events import (
            BillingSessionStarted, ResourceConsumed, BillingSessionClosed, BillingSessionSettled,
        )
        from app.domain.events.payment_events import (
            PaymentReceived, PaymentVerified, PaymentFailed, InvoiceGenerated, InvoicePaid,
        )

        event_type_map = {
            "AgentRegistered": AgentRegistered,
            "AgentDelegated": AgentDelegated,
            "AgentDelegationRevoked": AgentDelegationRevoked,
            "AgentReputationUpdated": AgentReputationUpdated,
            "BillingSessionStarted": BillingSessionStarted,
            "ResourceConsumed": ResourceConsumed,
            "BillingSessionClosed": BillingSessionClosed,
            "BillingSessionSettled": BillingSessionSettled,
            "PaymentReceived": PaymentReceived,
            "PaymentVerified": PaymentVerified,
            "PaymentFailed": PaymentFailed,
            "InvoiceGenerated": InvoiceGenerated,
            "InvoicePaid": InvoicePaid,
        }

        event_cls = event_type_map.get(row.event_type)
        if event_cls is None:
            raise ValueError(f"Unknown event type: {row.event_type}")

        data = json.loads(row.data) if isinstance(row.data, str) else row.data
        event = event_cls.__new__(event_cls)
        event.event_id = row.event_id
        event.aggregate_id = row.aggregate_id
        event.occurred_at = row.occurred_at if isinstance(row.occurred_at, datetime) else datetime.fromisoformat(row.occurred_at)
        event.data = data
        return event
