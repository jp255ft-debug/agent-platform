"""Unit tests for the API keys endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status
from datetime import datetime, timezone


@pytest.fixture
def mock_repo():
    """Create a mock API key repository."""
    repo = AsyncMock()
    repo.load_agent_keys = AsyncMock()
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock()
    request.headers = {"X-API-Key": "key-123.testkey"}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.state = MagicMock()
    return request


class TestCreateAPIKey:
    """Tests for POST /api/v1/agents/{agent_id}/api-keys"""

    @patch("app.api.v1.endpoints.api_keys.generate_api_key")
    @patch("app.api.v1.endpoints.api_keys.uuid.uuid4")
    async def test_create_api_key_success(
        self, mock_uuid, mock_generate_key, mock_repo, mock_request
    ):
        """Test successful API key creation."""
        from app.api.v1.endpoints.api_keys import create_api_key
        from app.api.v1.schemas.api_keys import APIKeyCreateRequest

        mock_uuid.return_value = "new-key-id"
        mock_generate_key.return_value = ("plain_key_value", "hashed_key_value")

        # Mock aggregate
        mock_aggregate = MagicMock()
        mock_aggregate.keys = [
            MagicMock(
                key_id="new-key-id",
                expires_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
            )
        ]
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)

        request = APIKeyCreateRequest(expires_in_days=90)

        with patch(
            "app.api.v1.endpoints.api_keys.validate_api_key",
            return_value="agent-123",
        ):
            response = await create_api_key(
                agent_id="agent-123",
                request=request,
                repo=mock_repo,
                authenticated_agent="agent-123",
                x_bootstrap_key=None,
            )

        assert response.key_id == "new-key-id"
        assert response.plain_key == "plain_key_value"
        assert response.agent_id == "agent-123"
        mock_repo.save.assert_awaited_once()

    async def test_create_api_key_wrong_agent(self, mock_repo, mock_request):
        """Test creating API key for another agent raises error."""
        from app.api.v1.endpoints.api_keys import create_api_key
        from app.api.v1.schemas.api_keys import APIKeyCreateRequest
        from app.core.exceptions import AuthenticationError

        request = APIKeyCreateRequest(expires_in_days=90)

        with pytest.raises(AuthenticationError):
            await create_api_key(
                agent_id="agent-456",
                request=request,
                repo=mock_repo,
                authenticated_agent="agent-123",
                x_bootstrap_key=None,
            )


class TestListAPIKeys:
    """Tests for GET /api/v1/agents/{agent_id}/api-keys"""

    async def test_list_api_keys_success(self, mock_repo, mock_request):
        """Test listing API keys successfully."""
        from app.api.v1.endpoints.api_keys import list_api_keys

        mock_aggregate = MagicMock()
        mock_aggregate.keys = [
            MagicMock(
                key_id="key-1",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                revoked=False,
                revoked_at=None,
                expired=False,
            ),
            MagicMock(
                key_id="key-2",
                created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                expires_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                revoked=True,
                revoked_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                expired=False,
            ),
        ]
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)

        response = await list_api_keys(
            agent_id="agent-123",
            repo=mock_repo,
            authenticated_agent="agent-123",
        )

        assert response.agent_id == "agent-123"
        assert len(response.keys) == 2
        assert response.keys[0].key_id == "key-1"
        assert response.keys[1].key_id == "key-2"

    async def test_list_api_keys_wrong_agent(self, mock_repo, mock_request):
        """Test listing API keys for another agent raises error."""
        from app.api.v1.endpoints.api_keys import list_api_keys
        from app.core.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            await list_api_keys(
                agent_id="agent-456",
                repo=mock_repo,
                authenticated_agent="agent-123",
            )


class TestRevokeAPIKey:
    """Tests for POST /api/v1/agents/{agent_id}/api-keys/{key_id}/revoke"""

    async def test_revoke_api_key_success(self, mock_repo, mock_request):
        """Test revoking an API key successfully."""
        from app.api.v1.endpoints.api_keys import revoke_api_key
        from app.api.v1.schemas.api_keys import APIKeyRevokeRequest

        mock_aggregate = MagicMock()
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)

        request = APIKeyRevokeRequest(reason="compromised")

        response = await revoke_api_key(
            agent_id="agent-123",
            key_id="key-1",
            request=request,
            repo=mock_repo,
            authenticated_agent="agent-123",
        )

        assert response["status"] == "revoked"
        assert response["key_id"] == "key-1"
        assert response["reason"] == "compromised"
        mock_aggregate.revoke_key.assert_called_once_with("key-1", reason="compromised")
        mock_repo.save.assert_awaited_once()

    async def test_revoke_api_key_wrong_agent(self, mock_repo, mock_request):
        """Test revoking API key for another agent raises error."""
        from app.api.v1.endpoints.api_keys import revoke_api_key
        from app.api.v1.schemas.api_keys import APIKeyRevokeRequest
        from app.core.exceptions import AuthenticationError

        request = APIKeyRevokeRequest(reason="manual")

        with pytest.raises(AuthenticationError):
            await revoke_api_key(
                agent_id="agent-456",
                key_id="key-1",
                request=request,
                repo=mock_repo,
                authenticated_agent="agent-123",
            )


class TestRotateAPIKey:
    """Tests for POST /api/v1/agents/{agent_id}/api-keys/{key_id}/rotate"""

    @patch("app.api.v1.endpoints.api_keys.generate_api_key")
    @patch("app.api.v1.endpoints.api_keys.uuid.uuid4")
    async def test_rotate_api_key_success(
        self, mock_uuid, mock_generate_key, mock_repo, mock_request
    ):
        """Test rotating an API key successfully."""
        from app.api.v1.endpoints.api_keys import rotate_api_key

        mock_uuid.return_value = "new-key-id-2"
        mock_generate_key.return_value = ("new_plain_key", "new_hashed_key")

        mock_aggregate = MagicMock()
        mock_aggregate.keys = [
            MagicMock(
                key_id="new-key-id-2",
                expires_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
            )
        ]
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)

        response = await rotate_api_key(
            agent_id="agent-123",
            key_id="key-1",
            repo=mock_repo,
            authenticated_agent="agent-123",
        )

        assert response.new_key_id == "new-key-id-2"
        assert response.plain_key == "new_plain_key"
        assert response.old_key_id == "key-1"
        mock_aggregate.rotate_key.assert_called_once()
        mock_repo.save.assert_awaited_once()

    async def test_rotate_api_key_wrong_agent(self, mock_repo, mock_request):
        """Test rotating API key for another agent raises error."""
        from app.api.v1.endpoints.api_keys import rotate_api_key
        from app.core.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            await rotate_api_key(
                agent_id="agent-456",
                key_id="key-1",
                repo=mock_repo,
                authenticated_agent="agent-123",
            )
