"""Integration tests for API key management endpoints.

Tests:
    POST /api/v1/agents/{agent_id}/api-keys — Create API key
    GET  /api/v1/agents/{agent_id}/api-keys — List API keys
    POST /api/v1/agents/{agent_id}/api-keys/{key_id}/revoke — Revoke API key
    POST /api/v1/agents/{agent_id}/api-keys/{key_id}/rotate — Rotate API key
"""
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


class TestCreateAPIKey:
    """Tests for POST /api/v1/agents/{agent_id}/api-keys."""

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_create_api_key_success(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should create a new API key successfully."""
        mock_validate.return_value = "test-agent"

        # Create a proper mock aggregate with a `keys` list
        mock_aggregate = MagicMock()
        mock_aggregate.keys = []
        mock_aggregate.create = MagicMock()

        mock_repo = MagicMock()
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)
        mock_get_repo.return_value = mock_repo

        response = client.post("/api/v1/agents/test-agent/api-keys", json={
            "expires_in_days": 90,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["agent_id"] == "test-agent"
        assert "key_id" in data
        assert "plain_key" in data  # Plain key returned only once
        assert "expires_at" in data

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_create_api_key_wrong_agent(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should return 401 when creating key for another agent."""
        mock_validate.return_value = "test-agent"

        response = client.post("/api/v1/agents/other-agent/api-keys", json={
            "expires_in_days": 90,
        })
        # AuthenticationError has http_status=401
        assert response.status_code == 401

    def test_create_api_key_invalid_payload(self, client: TestClient):
        """Should return 422 for invalid payload."""
        response = client.post("/api/v1/agents/test-agent/api-keys", json={
            "expires_in_days": -1,  # Invalid (must be >= 1)
        })
        assert response.status_code == 422


class TestListAPIKeys:
    """Tests for GET /api/v1/agents/{agent_id}/api-keys."""

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_list_api_keys_empty(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should return empty list when no keys exist."""
        mock_validate.return_value = "test-agent"

        mock_aggregate = MagicMock()
        mock_aggregate.keys = []

        mock_repo = MagicMock()
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)
        mock_get_repo.return_value = mock_repo

        response = client.get("/api/v1/agents/test-agent/api-keys")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test-agent"
        assert data["keys"] == []

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_list_api_keys_wrong_agent(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should return 401 when listing keys for another agent."""
        mock_validate.return_value = "test-agent"

        response = client.get("/api/v1/agents/other-agent/api-keys")
        # AuthenticationError has http_status=401
        assert response.status_code == 401


class TestRevokeAPIKey:
    """Tests for POST /api/v1/agents/{agent_id}/api-keys/{key_id}/revoke."""

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_revoke_api_key_success(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should revoke an API key successfully."""
        mock_validate.return_value = "test-agent"

        mock_aggregate = MagicMock()
        mock_aggregate.keys = []

        mock_repo = MagicMock()
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)
        mock_get_repo.return_value = mock_repo

        response = client.post(
            "/api/v1/agents/test-agent/api-keys/some-key/revoke",
            json={"reason": "compromised"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "revoked"
        assert data["key_id"] == "some-key"
        assert data["reason"] == "compromised"

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_revoke_api_key_wrong_agent(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should return 401 when revoking key for another agent."""
        mock_validate.return_value = "test-agent"

        response = client.post(
            "/api/v1/agents/other-agent/api-keys/some-key/revoke",
            json={"reason": "compromised"},
        )
        # AuthenticationError has http_status=401
        assert response.status_code == 401


class TestRotateAPIKey:
    """Tests for POST /api/v1/agents/{agent_id}/api-keys/{key_id}/rotate."""

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_rotate_api_key_success(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should rotate an API key successfully."""
        mock_validate.return_value = "test-agent"

        mock_aggregate = MagicMock()
        mock_aggregate.keys = []

        mock_repo = MagicMock()
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)
        mock_get_repo.return_value = mock_repo

        response = client.post(
            "/api/v1/agents/test-agent/api-keys/some-key/rotate",
        )
        assert response.status_code == 200
        data = response.json()
        assert "new_key_id" in data
        assert "plain_key" in data
        assert "old_key_id" in data
        assert data["old_key_id"] == "some-key"

    @patch("app.api.v1.endpoints.api_keys.get_api_key_repository")
    @patch("app.api.v1.endpoints.api_keys.validate_api_key")
    def test_rotate_api_key_wrong_agent(
        self, mock_validate, mock_get_repo, client: TestClient,
    ):
        """Should return 401 when rotating key for another agent."""
        mock_validate.return_value = "test-agent"

        response = client.post(
            "/api/v1/agents/other-agent/api-keys/some-key/rotate",
        )
        # AuthenticationError has http_status=401
        assert response.status_code == 401
