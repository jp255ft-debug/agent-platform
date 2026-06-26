"""Integration tests for agent management endpoints.

Tests:
    POST /api/v1/agents — Register a new agent
    GET  /api/v1/agents/{agent_id} — Get agent details
    POST /api/v1/agents/{agent_id}/delegate — Delegate agent
    POST /api/v1/agents/{agent_id}/revoke-delegation — Revoke delegation
    POST /api/v1/agents/{agent_id}/reputation — Update reputation
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestRegisterAgent:
    """Tests for POST /api/v1/agents."""

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_register_agent_success(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should register a new agent successfully."""
        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_register_agent = AsyncMock()

        response = client.post("/api/v1/agents", json={
            "agent_id": "agent-123",
            "owner_address": "0x1234567890abcdef1234567890abcdef12345678",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["agent_id"] == "agent-123"
        assert data["owner_address"] == "0x1234567890abcdef1234567890abcdef12345678"

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_register_agent_with_delegation(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should register agent with optional delegation address."""
        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_register_agent = AsyncMock()

        response = client.post("/api/v1/agents", json={
            "agent_id": "agent-456",
            "owner_address": "0xabcdef1234567890abcdef1234567890abcdef12",
            "delegation_address": "0xdelegation1234567890abcdef1234567890abcdef",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["agent_id"] == "agent-456"
        assert data["delegation_address"] == "0xdelegation1234567890abcdef1234567890abcdef"

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_register_agent_duplicate(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should return 409 when agent already exists."""
        from app.core.exceptions import AgentAlreadyExistsError

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_register_agent = AsyncMock(
            side_effect=AgentAlreadyExistsError("agent-duplicate")
        )

        response = client.post("/api/v1/agents", json={
            "agent_id": "agent-duplicate",
            "owner_address": "0x1234567890abcdef1234567890abcdef12345678",
        })
        assert response.status_code == 409

    def test_register_agent_invalid_payload(self, client: TestClient):
        """Should return 422 for missing required fields."""
        response = client.post("/api/v1/agents", json={
            "agent_id": "agent-789",
            # missing owner_address
        })
        assert response.status_code == 422


class TestGetAgent:
    """Tests for GET /api/v1/agents/{agent_id}."""

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    def test_get_agent_found(self, mock_store_cls, client: TestClient):
        """Should return agent details when agent exists."""
        from app.domain.events.agent_events import AgentRegistered

        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[
            AgentRegistered(
                agent_id="agent-found",
                owner_address="0x1234567890abcdef1234567890abcdef12345678",
            ),
        ])

        response = client.get("/api/v1/agents/agent-found")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-found"
        assert data["owner_address"] == "0x1234567890abcdef1234567890abcdef12345678"

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    def test_get_agent_not_found(self, mock_store_cls, client: TestClient):
        """Should return 404 when agent does not exist."""
        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[])

        response = client.get("/api/v1/agents/non-existent-agent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDelegateAgent:
    """Tests for POST /api/v1/agents/{agent_id}/delegate."""

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_delegate_agent_success(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should delegate agent successfully."""
        from app.domain.events.agent_events import AgentRegistered

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_delegate_agent = AsyncMock()

        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[
            AgentRegistered(
                agent_id="agent-delegate",
                owner_address="0x1234567890abcdef1234567890abcdef12345678",
            ),
        ])

        response = client.post("/api/v1/agents/agent-delegate/delegate", json={
            "delegate_address": "0xdelegate1234567890abcdef1234567890abcdef",
            "expires_at": "2027-01-01T00:00:00Z",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-delegate"

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_delegate_agent_not_found(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should return 404 when delegating non-existent agent."""
        from app.core.exceptions import AgentNotFoundError

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_delegate_agent = AsyncMock(
            side_effect=AgentNotFoundError("non-existent")
        )

        response = client.post("/api/v1/agents/non-existent/delegate", json={
            "delegate_address": "0xdelegate1234567890abcdef1234567890abcdef",
            "expires_at": "2027-01-01T00:00:00Z",
        })
        assert response.status_code == 404


class TestRevokeDelegation:
    """Tests for POST /api/v1/agents/{agent_id}/revoke-delegation."""

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_revoke_delegation_success(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should revoke delegation successfully."""
        from app.domain.events.agent_events import AgentRegistered

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_revoke_delegation = AsyncMock()

        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[
            AgentRegistered(
                agent_id="agent-revoke",
                owner_address="0x1234567890abcdef1234567890abcdef12345678",
            ),
        ])

        response = client.post("/api/v1/agents/agent-revoke/revoke-delegation")
        assert response.status_code == 200

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_revoke_delegation_not_found(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should return 404 when revoking delegation for non-existent agent."""
        from app.core.exceptions import AgentNotFoundError

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_revoke_delegation = AsyncMock(
            side_effect=AgentNotFoundError("non-existent")
        )

        response = client.post("/api/v1/agents/non-existent/revoke-delegation")
        assert response.status_code == 404


class TestUpdateReputation:
    """Tests for POST /api/v1/agents/{agent_id}/reputation."""

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_update_reputation_success(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should update agent reputation successfully."""
        from app.domain.events.agent_events import AgentRegistered

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_update_reputation = AsyncMock()

        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[
            AgentRegistered(
                agent_id="agent-rep",
                owner_address="0x1234567890abcdef1234567890abcdef12345678",
            ),
        ])

        response = client.post("/api/v1/agents/agent-rep/reputation", json={
            "new_score": 85,
            "reason": "good_performance",
        })
        assert response.status_code == 200

    @patch("app.api.v1.endpoints.agents.PostgresEventStore")
    @patch("app.api.v1.endpoints.agents.CommandHandlers")
    def test_update_reputation_not_found(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should return 404 when updating reputation for non-existent agent."""
        from app.core.exceptions import AgentNotFoundError

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_update_reputation = AsyncMock(
            side_effect=AgentNotFoundError("non-existent")
        )

        response = client.post("/api/v1/agents/non-existent/reputation", json={
            "new_score": 85,
            "reason": "good_performance",
        })
        assert response.status_code == 404

    def test_update_reputation_invalid_score(self, client: TestClient):
        """Should return 422 for invalid reputation score."""
        response = client.post("/api/v1/agents/agent-rep/reputation", json={
            "new_score": 150,  # Invalid: max is 100
            "reason": "test",
        })
        assert response.status_code == 422
