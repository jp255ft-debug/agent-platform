"""Integration tests for resource consumption endpoints.

Tests:
    POST /api/v1/consume — Consume a resource with x402 payment
    GET  /api/v1/consume/sessions/{session_id} — Get billing session
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestConsumeResource:
    """Tests for POST /api/v1/consume."""

    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    @patch("app.api.v1.endpoints.consume.CommandHandlers")
    def test_consume_resource_success(
        self, mock_handlers_cls, mock_store_cls, mock_limiter_cls, mock_idemp_cls,
        client: TestClient,
    ):
        """Should consume a resource successfully."""
        mock_idemp = mock_idemp_cls.return_value
        mock_idemp.is_processed = AsyncMock(return_value=False)
        mock_idemp.mark_processed = AsyncMock()

        mock_limiter = mock_limiter_cls.return_value
        mock_limiter.check_rate_limit = AsyncMock(return_value=True)
        mock_limiter.get_remaining_tokens = AsyncMock(return_value=900)

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_consume_resource = AsyncMock(return_value="session-123")

        response = client.post("/api/v1/consume", json={
            "agent_id": "agent-consume",
            "resource_type": "compute",
            "amount": 100,
            "x402_payment": {"verified": True, "tx_hash": "0xabc123"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "consumed"
        assert data["total_consumed"] == 100
        assert data["session_id"] == "session-123"
        assert data["remaining_tokens"] == 900

    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    @patch("app.api.v1.endpoints.consume.CommandHandlers")
    def test_consume_resource_with_idempotency(
        self, mock_handlers_cls, mock_store_cls, mock_limiter_cls, mock_idemp_cls,
        client: TestClient,
    ):
        """Should handle idempotent requests."""
        mock_idemp = mock_idemp_cls.return_value
        mock_idemp.is_processed = AsyncMock(return_value=False)
        mock_idemp.mark_processed = AsyncMock()
        mock_idemp.get_result = AsyncMock(return_value=None)  # Must be AsyncMock

        mock_limiter = mock_limiter_cls.return_value
        mock_limiter.check_rate_limit = AsyncMock(return_value=True)
        mock_limiter.get_remaining_tokens = AsyncMock(return_value=950)

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_consume_resource = AsyncMock(return_value="session-456")

        payload = {
            "agent_id": "agent-idempotent",
            "resource_type": "compute",
            "amount": 50,
            "x402_payment": {"verified": True, "tx_hash": "0xdef456"},
            "idempotency_key": "unique-key-123",
        }

        # First request succeeds
        response1 = client.post("/api/v1/consume", json=payload)
        assert response1.status_code == 200

        # Second request with same key should return 409
        mock_idemp.is_processed = AsyncMock(return_value=True)
        response2 = client.post("/api/v1/consume", json=payload)
        assert response2.status_code == 409

    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    def test_consume_resource_rate_limited(
        self, mock_limiter_cls, mock_idemp_cls, client: TestClient,
    ):
        """Should return 429 when rate limit exceeded."""
        mock_idemp = mock_idemp_cls.return_value
        mock_idemp.is_processed = AsyncMock(return_value=False)

        mock_limiter = mock_limiter_cls.return_value
        mock_limiter.check_rate_limit = AsyncMock(return_value=False)

        response = client.post("/api/v1/consume", json={
            "agent_id": "agent-limited",
            "resource_type": "compute",
            "amount": 100,
            "x402_payment": {"verified": True, "tx_hash": "0xabc123"},
        })
        assert response.status_code == 429

    def test_consume_resource_invalid_payload(self, client: TestClient):
        """Should return 422 for invalid payload."""
        response = client.post("/api/v1/consume", json={
            "agent_id": "agent-invalid",
            # missing resource_type, amount, x402_payment
        })
        assert response.status_code == 422

    def test_consume_resource_zero_amount(self, client: TestClient):
        """Should return 422 for zero amount (must be > 0)."""
        response = client.post("/api/v1/consume", json={
            "agent_id": "agent-zero",
            "resource_type": "compute",
            "amount": 0,
            "x402_payment": {"verified": True},
        })
        assert response.status_code == 422


class TestGetBillingSession:
    """Tests for GET /api/v1/consume/sessions/{session_id}."""

    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    def test_get_billing_session_found(self, mock_store_cls, client: TestClient):
        """Should return billing session when it exists."""
        from app.domain.events.billing_events import BillingSessionStarted

        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[
            BillingSessionStarted(
                session_id="session-found",
                agent_id="agent-session",
                resource_type="compute",
            ),
        ])

        response = client.get("/api/v1/consume/sessions/session-found")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-found"
        assert data["agent_id"] == "agent-session"
        assert data["resource_type"] == "compute"
        assert data["status"] == "active"

    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    def test_get_billing_session_not_found(self, mock_store_cls, client: TestClient):
        """Should return 404 when session does not exist."""
        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[])

        response = client.get("/api/v1/consume/sessions/non-existent-session")
        assert response.status_code == 404
