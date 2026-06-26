"""Unit tests for core authentication module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHashAPIKey:
    """Tests for hash_api_key function."""

    def test_hash_api_key_returns_string(self):
        """Test hash_api_key returns a string."""
        from app.core.auth import hash_api_key

        result = hash_api_key("test-key-123")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_api_key_different_for_same_key(self):
        """Test hash_api_key produces different hashes for same input (salt)."""
        from app.core.auth import hash_api_key

        result1 = hash_api_key("test-key-123")
        result2 = hash_api_key("test-key-123")
        assert result1 != result2


class TestVerifyAPIKey:
    """Tests for verify_api_key function."""

    def test_verify_api_key_correct(self):
        """Test verify_api_key returns True for correct key."""
        from app.core.auth import hash_api_key, verify_api_key

        plain = "my-secret-key"
        hashed = hash_api_key(plain)
        assert verify_api_key(plain, hashed) is True

    def test_verify_api_key_incorrect(self):
        """Test verify_api_key returns False for incorrect key."""
        from app.core.auth import hash_api_key, verify_api_key

        hashed = hash_api_key("correct-key")
        assert verify_api_key("wrong-key", hashed) is False


class TestGenerateAPIKey:
    """Tests for generate_api_key function."""

    def test_generate_api_key_returns_tuple(self):
        """Test generate_api_key returns a tuple of two strings."""
        from app.core.auth import generate_api_key

        plain, hashed = generate_api_key()
        assert isinstance(plain, str)
        assert isinstance(hashed, str)
        assert len(plain) > 0
        assert len(hashed) > 0

    def test_generate_api_key_plain_is_urlsafe(self):
        """Test generate_api_key plain key is URL-safe."""
        from app.core.auth import generate_api_key

        plain, _ = generate_api_key()
        # URL-safe base64 only contains alphanumeric, -, and _
        import re
        assert re.match(r"^[A-Za-z0-9\-_]+$", plain)

    def test_generate_api_key_plain_matches_hash(self):
        """Test generate_api_key plain key verifies against hash."""
        from app.core.auth import generate_api_key, verify_api_key

        plain, hashed = generate_api_key()
        assert verify_api_key(plain, hashed) is True


class TestGetAPIKeyRepository:
    """Tests for get_api_key_repository dependency."""

    @patch("app.core.auth.APIKeyRepository")
    async def test_get_api_key_repository(self, mock_repo_cls):
        """Test get_api_key_repository creates repository with db and redis."""
        from app.core.auth import get_api_key_repository

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = await get_api_key_repository(mock_db, mock_redis)
        mock_repo_cls.assert_called_once_with(db=mock_db, redis=mock_redis)
        assert result == mock_repo_cls.return_value


class TestValidateAPIKey:
    """Tests for validate_api_key dependency."""

    @patch("app.core.auth.get_api_key_repository")
    async def test_validate_api_key_success(self, mock_get_repo):
        """Test successful API key validation."""
        from app.core.auth import validate_api_key

        mock_request = MagicMock()
        mock_request.headers = {"X-API-Key": "key-123.plain_key_value"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state = MagicMock()

        mock_repo = AsyncMock()
        mock_repo.get_key_hash = AsyncMock(return_value=("agent-123", "stored_hash"))
        mock_get_repo.return_value = mock_repo

        mock_aggregate = MagicMock()
        mock_aggregate.is_valid = MagicMock(return_value=True)
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)

        with patch("app.core.auth.verify_api_key", return_value=True):
            result = await validate_api_key(mock_request, None, mock_repo)

        assert result == "agent-123"
        assert mock_request.state.agent_id == "agent-123"
        mock_aggregate.record_usage.assert_called_once()
        mock_repo.save.assert_awaited_once()

    @patch("app.core.auth.get_api_key_repository")
    async def test_validate_api_key_missing(self, mock_get_repo):
        """Test validation returns None when API key is missing (bootstrap mode)."""
        from app.core.auth import validate_api_key

        mock_request = MagicMock()
        mock_request.headers = {}

        result = await validate_api_key(mock_request, None, AsyncMock())
        assert result is None

    @patch("app.core.auth.get_api_key_repository")
    async def test_validate_api_key_invalid_format(self, mock_get_repo):
        """Test validation fails when API key format is invalid."""
        from app.core.auth import validate_api_key
        from app.core.exceptions import AuthenticationError

        mock_request = MagicMock()
        mock_request.headers = {"X-API-Key": "invalid-key-no-dot"}

        with pytest.raises(AuthenticationError) as exc:
            await validate_api_key(mock_request, None, AsyncMock())
        assert "Invalid API key format" in str(exc.value)

    @patch("app.core.auth.get_api_key_repository")
    async def test_validate_api_key_not_found(self, mock_get_repo):
        """Test validation fails when key_id is not found."""
        from app.core.auth import validate_api_key
        from app.core.exceptions import AuthenticationError

        mock_request = MagicMock()
        mock_request.headers = {"X-API-Key": "unknown-key.plain"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_repo = AsyncMock()
        mock_repo.get_key_hash = AsyncMock(return_value=(None, None))
        mock_get_repo.return_value = mock_repo

        with pytest.raises(AuthenticationError) as exc:
            await validate_api_key(mock_request, None, mock_repo)
        assert "API key not found" in str(exc.value)

    @patch("app.core.auth.get_api_key_repository")
    async def test_validate_api_key_invalid_key(self, mock_get_repo):
        """Test validation fails when plain key doesn't match hash."""
        from app.core.auth import validate_api_key
        from app.core.exceptions import AuthenticationError

        mock_request = MagicMock()
        mock_request.headers = {"X-API-Key": "key-123.wrong_plain"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_repo = AsyncMock()
        mock_repo.get_key_hash = AsyncMock(return_value=("agent-123", "stored_hash"))
        mock_get_repo.return_value = mock_repo

        with patch("app.core.auth.verify_api_key", return_value=False):
            with pytest.raises(AuthenticationError) as exc:
                await validate_api_key(mock_request, None, mock_repo)
        assert "Invalid API key" in str(exc.value)

    @patch("app.core.auth.get_api_key_repository")
    async def test_validate_api_key_revoked_or_expired(self, mock_get_repo):
        """Test validation fails when key is revoked or expired."""
        from app.core.auth import validate_api_key
        from app.core.exceptions import AuthenticationError

        mock_request = MagicMock()
        mock_request.headers = {"X-API-Key": "key-123.plain_key_value"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_repo = AsyncMock()
        mock_repo.get_key_hash = AsyncMock(return_value=("agent-123", "stored_hash"))
        mock_get_repo.return_value = mock_repo

        mock_aggregate = MagicMock()
        mock_aggregate.is_valid = MagicMock(return_value=False)
        mock_repo.load_agent_keys = AsyncMock(return_value=mock_aggregate)

        with patch("app.core.auth.verify_api_key", return_value=True):
            with pytest.raises(AuthenticationError) as exc:
                await validate_api_key(mock_request, None, mock_repo)
        assert "revoked or expired" in str(exc.value)


class TestGetCurrentAgent:
    """Tests for get_current_agent dependency."""

    async def test_get_current_agent(self):
        """Test get_current_agent returns agent_id."""
        from app.core.auth import get_current_agent

        result = await get_current_agent("agent-123")
        assert result == "agent-123"
