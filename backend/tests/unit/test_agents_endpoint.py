"""Unit tests for agents endpoint."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.agents import register_agent, get_agent, delegate_agent, revoke_delegation, update_reputation
from app.api.v1.schemas.agents import AgentCreate, AgentDelegateRequest, AgentReputationUpdate
from app.core.exceptions import AgentAlreadyExistsError, AgentNotFoundError, DomainError


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_event_store():
    store = MagicMock()
    store.load_stream = AsyncMock()
    return store


@pytest.fixture
def mock_command_handlers():
    handlers = MagicMock()
    handlers.handle_register_agent = AsyncMock()
    handlers.handle_delegate_agent = AsyncMock()
    handlers.handle_revoke_delegation = AsyncMock()
    handlers.handle_update_reputation = AsyncMock()
    return handlers


class TestRegisterAgent:
    """Test POST /agents endpoint."""

    async def test_register_agent_success(self, mock_db, mock_command_handlers):
        body = AgentCreate(
            agent_id="agent-1",
            owner_address="0xabc",
            delegation_address="0xdef",
        )

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            response = await register_agent(body, db=mock_db)

        assert response.agent_id == "agent-1"
        assert response.owner_address == "0xabc"
        assert response.delegation_address == "0xdef"
        mock_command_handlers.handle_register_agent.assert_awaited_once()

    async def test_register_agent_already_exists(self, mock_db, mock_command_handlers):
        body = AgentCreate(
            agent_id="agent-1",
            owner_address="0xabc",
        )
        mock_command_handlers.handle_register_agent.side_effect = AgentAlreadyExistsError("agent-1")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await register_agent(body, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    async def test_register_agent_domain_error(self, mock_db, mock_command_handlers):
        body = AgentCreate(
            agent_id="agent-1",
            owner_address="0xabc",
        )
        mock_command_handlers.handle_register_agent.side_effect = DomainError("Invalid data")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await register_agent(body, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestGetAgent:
    """Test GET /agents/{agent_id} endpoint."""

    async def test_get_agent_found(self, mock_db, mock_event_store):
        from app.domain.events.agent_events import AgentRegistered

        event = AgentRegistered(
            agent_id="agent-1",
            owner_address="0xabc",
            delegation_address="0xdef",
        )
        mock_event_store.load_stream.return_value = [event]

        with patch("app.api.v1.endpoints.agents.PostgresEventStore", return_value=mock_event_store):
            response = await get_agent("agent-1", db=mock_db)

        assert response.agent_id == "agent-1"
        assert response.owner_address == "0xabc"
        assert response.delegation_address == "0xdef"

    async def test_get_agent_not_found(self, mock_db, mock_event_store):
        mock_event_store.load_stream.return_value = []

        with patch("app.api.v1.endpoints.agents.PostgresEventStore", return_value=mock_event_store):
            with pytest.raises(HTTPException) as exc_info:
                await get_agent("nonexistent", db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Agent not found"


class TestDelegateAgent:
    """Test POST /agents/{agent_id}/delegate endpoint."""

    async def test_delegate_agent_success(self, mock_db, mock_command_handlers, mock_event_store):
        from app.domain.events.agent_events import AgentRegistered, AgentDelegated

        events = [
            AgentRegistered(agent_id="agent-1", owner_address="0xabc"),
            AgentDelegated(agent_id="agent-1", delegate_address="0xdef", expires_at=9999999999),
        ]
        mock_event_store.load_stream.return_value = events
        body = AgentDelegateRequest(delegate_address="0xdef", expires_at="9999999999")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with patch("app.api.v1.endpoints.agents.PostgresEventStore", return_value=mock_event_store):
                response = await delegate_agent("agent-1", body, db=mock_db)

        assert response.agent_id == "agent-1"
        mock_command_handlers.handle_delegate_agent.assert_awaited_once()

    async def test_delegate_agent_not_found(self, mock_db, mock_command_handlers):
        mock_command_handlers.handle_delegate_agent.side_effect = AgentNotFoundError("agent-1")
        body = AgentDelegateRequest(delegate_address="0xdef", expires_at="9999999999")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await delegate_agent("agent-1", body, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_delegate_agent_domain_error(self, mock_db, mock_command_handlers):
        mock_command_handlers.handle_delegate_agent.side_effect = DomainError("Invalid delegation")
        body = AgentDelegateRequest(delegate_address="0xdef", expires_at="9999999999")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await delegate_agent("agent-1", body, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestRevokeDelegation:
    """Test POST /agents/{agent_id}/revoke-delegation endpoint."""

    async def test_revoke_delegation_success(self, mock_db, mock_command_handlers, mock_event_store):
        from app.domain.events.agent_events import AgentRegistered

        mock_event_store.load_stream.return_value = [
            AgentRegistered(agent_id="agent-1", owner_address="0xabc"),
        ]

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with patch("app.api.v1.endpoints.agents.PostgresEventStore", return_value=mock_event_store):
                response = await revoke_delegation("agent-1", db=mock_db)

        assert response.agent_id == "agent-1"
        mock_command_handlers.handle_revoke_delegation.assert_awaited_once()

    async def test_revoke_delegation_not_found(self, mock_db, mock_command_handlers):
        mock_command_handlers.handle_revoke_delegation.side_effect = AgentNotFoundError("agent-1")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await revoke_delegation("agent-1", db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateReputation:
    """Test POST /agents/{agent_id}/reputation endpoint."""

    async def test_update_reputation_success(self, mock_db, mock_command_handlers, mock_event_store):
        from app.domain.events.agent_events import AgentRegistered, AgentReputationUpdated

        mock_event_store.load_stream.return_value = [
            AgentRegistered(agent_id="agent-1", owner_address="0xabc"),
            AgentReputationUpdated(agent_id="agent-1", new_score=85, reason="good"),
        ]
        body = AgentReputationUpdate(new_score=85, reason="good behavior")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with patch("app.api.v1.endpoints.agents.PostgresEventStore", return_value=mock_event_store):
                response = await update_reputation("agent-1", body, db=mock_db)

        assert response.agent_id == "agent-1"
        assert response.reputation_score == 85
        mock_command_handlers.handle_update_reputation.assert_awaited_once()

    async def test_update_reputation_not_found(self, mock_db, mock_command_handlers):
        mock_command_handlers.handle_update_reputation.side_effect = AgentNotFoundError("agent-1")
        body = AgentReputationUpdate(new_score=85, reason="test")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await update_reputation("agent-1", body, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_reputation_domain_error(self, mock_db, mock_command_handlers):
        mock_command_handlers.handle_update_reputation.side_effect = DomainError("Invalid score")
        body = AgentReputationUpdate(new_score=85, reason="test")

        with patch("app.api.v1.endpoints.agents._get_command_handlers", return_value=mock_command_handlers):
            with pytest.raises(HTTPException) as exc_info:
                await update_reputation("agent-1", body, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
