"""Unit tests for PostgresEventStore."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.repositories.event_store import PostgresEventStore
from app.core.exceptions import ConcurrencyError
from app.domain.events.agent_events import AgentRegistered
from app.domain.events.billing_events import BillingSessionStarted, ResourceConsumed, ResourceConsumedV2


@pytest.fixture
def session():
    # Use MagicMock instead of AsyncMock because session.begin() is a sync method
    # that returns an async context manager. AsyncMock would make begin() a coroutine.
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    # session.begin() must return an async context manager
    ctx_mgr = MagicMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=ctx_mgr)
    ctx_mgr.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin.return_value = ctx_mgr
    return mock_session


@pytest.fixture
def event_store(session):
    return PostgresEventStore(session)


class TestAppendEvents:
    async def test_append_events_success(self, event_store, session):
        events = [
            AgentRegistered(
                "agent-1",
                "0x1234",
            )
        ]
        await event_store.append_events("agent-1", events, expected_version=0)
        # No explicit transaction (session.begin) is used; OCC relies on
        # the UNIQUE(stream_id, version) constraint at the DB level.
        session.execute.assert_awaited_once()

    async def test_append_events_multiple(self, event_store, session):
        events = [
            AgentRegistered(
                "agent-1",
                "0x1234",
            ),
            BillingSessionStarted(
                "session-1",
                "agent-1",
                "tflops",
            ),
        ]
        await event_store.append_events("agent-1", events, expected_version=0)
        assert session.execute.await_count == 2

    async def test_append_events_concurrency_error(self, event_store, session):
        """Simulate IntegrityError due to unique constraint violation."""
        # orig must be a string that contains "uq_stream_version" for the check to work
        orig = MagicMock()
        orig.__str__.return_value = "duplicate key value violates unique constraint 'uq_stream_version'"
        session.execute.side_effect = IntegrityError(
            "INSERT INTO events ...",
            {},
            orig,
        )
        # Mock _get_latest_version to return actual version
        event_store._get_latest_version = AsyncMock(return_value=5)

        events = [
            AgentRegistered(
                "agent-1",
                "0x1234",
            )
        ]
        with pytest.raises(ConcurrencyError) as exc_info:
            await event_store.append_events("agent-1", events, expected_version=0)
        assert exc_info.value.details["aggregate_id"] == "agent-1"
        assert exc_info.value.details["expected_version"] == 0
        assert exc_info.value.details["actual_version"] == 5

    async def test_append_events_non_concurrency_error(self, event_store, session):
        """Non-concurrency IntegrityError should propagate."""
        session.execute.side_effect = IntegrityError(
            "INSERT INTO events ...",
            {},
            MagicMock(orig="violates foreign key constraint"),
        )
        events = [
            AgentRegistered(
                "agent-1",
                "0x1234",
            )
        ]
        with pytest.raises(IntegrityError):
            await event_store.append_events("agent-1", events, expected_version=0)


class TestLoadStream:
    async def test_load_stream_empty(self, event_store, session):
        session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
        events = await event_store.load_stream("agent-unknown")
        assert events == []

    async def test_load_stream_with_events(self, event_store, session):
        """Test loading events with proper row mock."""
        mock_row = MagicMock()
        mock_row.event_id = "evt-1"
        mock_row.stream_id = "agent-1"
        mock_row.version = 1
        mock_row.event_type = "AgentRegistered"
        mock_row.aggregate_id = "agent-1"
        mock_row.data = '{"agent_id": "agent-1", "owner_address": "0x1234", "delegation_address": null}'
        mock_row.occurred_at = datetime.now(timezone.utc)

        session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[mock_row]))
        events = await event_store.load_stream("agent-1")
        assert len(events) == 1
        assert isinstance(events[0], AgentRegistered)
        assert events[0].data["owner_address"] == "0x1234"

    async def test_load_stream_from_version(self, event_store, session):
        mock_row = MagicMock()
        mock_row.event_id = "evt-2"
        mock_row.stream_id = "agent-1"
        mock_row.version = 2
        mock_row.event_type = "BillingSessionStarted"
        mock_row.aggregate_id = "session-1"
        mock_row.data = '{"session_id": "session-1", "agent_id": "agent-1", "resource_type": "tflops"}'
        mock_row.occurred_at = datetime.now(timezone.utc)

        session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[mock_row]))
        events = await event_store.load_stream_from_version("agent-1", from_version=2)
        assert len(events) == 1
        assert isinstance(events[0], BillingSessionStarted)


class TestRowToEvent:
    async def test_row_to_event_agent_registered(self, event_store, session):
        mock_row = MagicMock()
        mock_row.event_id = "evt-1"
        mock_row.stream_id = "agent-1"
        mock_row.version = 1
        mock_row.event_type = "AgentRegistered"
        mock_row.aggregate_id = "agent-1"
        mock_row.data = '{"agent_id": "agent-1", "owner_address": "0x1234", "delegation_address": null}'
        mock_row.occurred_at = datetime.now(timezone.utc)

        event = event_store._row_to_event(mock_row)
        assert isinstance(event, AgentRegistered)
        assert event.aggregate_id == "agent-1"

    async def test_row_to_event_resource_consumed_v1(self, event_store, session):
        """Test that V1 ResourceConsumed is properly upcasted to V2."""
        mock_row = MagicMock()
        mock_row.event_id = "evt-2"
        mock_row.stream_id = "session-1"
        mock_row.version = 2
        mock_row.event_type = "ResourceConsumed"
        mock_row.aggregate_id = "session-1"
        mock_row.data = '{"session_id": "session-1", "agent_id": "agent-1", "amount": 50, "resource_type": "tflops"}'
        mock_row.occurred_at = datetime.now(timezone.utc)

        event = event_store._row_to_event(mock_row)
        # V1 ResourceConsumed is upcasted to ResourceConsumedV2
        assert isinstance(event, ResourceConsumedV2)
        assert event.data["amount"] == 50
        assert event.data["cost_micro_usdc"] == 0  # default for V1

    async def test_row_to_event_resource_consumed_v2(self, event_store, session):
        """Test that V2 ResourceConsumedV2 is properly deserialized."""
        mock_row = MagicMock()
        mock_row.event_id = "evt-3"
        mock_row.stream_id = "session-1"
        mock_row.version = 3
        mock_row.event_type = "ResourceConsumedV2"
        mock_row.aggregate_id = "session-1"
        mock_row.data = '{"session_id": "session-1", "agent_id": "agent-1", "amount": 100, "cost_micro_usdc": 50000, "provider_id": "provider-1", "resource_type": "tflops"}'
        mock_row.occurred_at = datetime.now(timezone.utc)

        event = event_store._row_to_event(mock_row)
        assert isinstance(event, ResourceConsumedV2)
        assert event.data["cost_micro_usdc"] == 50000
        assert event.data["provider_id"] == "provider-1"

    async def test_row_to_event_unknown_type(self, event_store, session):
        mock_row = MagicMock()
        mock_row.event_id = "evt-4"
        mock_row.stream_id = "unknown"
        mock_row.version = 1
        mock_row.event_type = "UnknownEventType"
        mock_row.aggregate_id = "unknown"
        mock_row.data = "{}"
        mock_row.occurred_at = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Unknown event type after upcast"):
            event_store._row_to_event(mock_row)


class TestGetLatestVersion:
    async def test_get_latest_version_returns_zero_when_empty(self, event_store, session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        session.execute.return_value = mock_result

        version = await event_store._get_latest_version("agent-unknown")
        assert version == 0

    async def test_get_latest_version_returns_max(self, event_store, session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        session.execute.return_value = mock_result

        version = await event_store._get_latest_version("agent-1")
        assert version == 5
