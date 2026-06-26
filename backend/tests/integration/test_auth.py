"""Integration tests for API key authentication."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.auth import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    validate_api_key,
)
from app.core.exceptions import AuthenticationError


class TestAPIKeyCrypto:
    """Tests for API key cryptographic utilities."""

    def test_generate_api_key_returns_pair(self):
        plain, hashed = generate_api_key()
        assert len(plain) == 43  # 32 bytes → base64url
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_hash_and_verify_roundtrip(self):
        plain, hashed = generate_api_key()
        assert verify_api_key(plain, hashed) is True

    def test_verify_wrong_key_returns_false(self):
        plain, hashed = generate_api_key()
        assert verify_api_key("wrong_key", hashed) is False

    def test_hash_is_deterministic(self):
        """Bcrypt hashes are salted, so same input produces different hashes."""
        plain = "test_key_123"
        hash1 = hash_api_key(plain)
        hash2 = hash_api_key(plain)
        assert hash1 != hash2  # different salts
        assert verify_api_key(plain, hash1) is True
        assert verify_api_key(plain, hash2) is True


class TestValidateAPIKey:
    """Tests for validate_api_key dependency."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self):
        request = MagicMock()
        request.headers = {}
        request.client = None

        with pytest.raises(AuthenticationError) as exc_info:
            await validate_api_key(request, api_key_header=None)

        assert exc_info.value.code == "AUTHENTICATION_FAILED"
        assert "Missing API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_format_raises_error(self):
        request = MagicMock()
        request.headers = {"X-API-Key": "invalid_format"}
        request.client = None

        with pytest.raises(AuthenticationError) as exc_info:
            await validate_api_key(request)

        assert "Invalid API key format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_key_not_found_raises_error(self):
        request = MagicMock()
        request.headers = {"X-API-Key": "unknown_key.plain"}
        request.client = None

        repo = AsyncMock()
        repo.get_key_hash = AsyncMock(return_value=(None, None))

        with pytest.raises(AuthenticationError) as exc_info:
            await validate_api_key(request, repo=repo)

        assert "API key not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_key_raises_error(self):
        """Test that a wrong plain key is rejected."""
        # Generate a real bcrypt hash for a different key
        from app.core.auth import hash_api_key
        real_hash = hash_api_key("correct_key")

        request = MagicMock()
        request.headers = {"X-API-Key": "key123.wrong_key"}
        request.client = None

        repo = AsyncMock()
        repo.get_key_hash = AsyncMock(return_value=("agent-123", real_hash))

        with pytest.raises(AuthenticationError) as exc_info:
            await validate_api_key(request, repo=repo)

        assert "Invalid API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoked_key_raises_error(self):
        """Test that a revoked key is rejected."""
        from app.domain.aggregates.api_key import APIKeyAggregate

        # Create a key and revoke it
        aggregate = APIKeyAggregate(agent_id="agent-123")
        aggregate.create(key_id="key123", key_hash="stored_hash")
        aggregate.revoke_key("key123")

        request = MagicMock()
        request.headers = {"X-API-Key": "key123.plain_key"}
        request.client = None

        repo = AsyncMock()
        repo.get_key_hash = AsyncMock(return_value=("agent-123", "stored_hash"))
        repo.load_agent_keys = AsyncMock(return_value=aggregate)

        with patch("app.core.auth.verify_api_key", return_value=True):
            with pytest.raises(AuthenticationError) as exc_info:
                await validate_api_key(request, repo=repo)

        assert "revoked or expired" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_valid_key_returns_agent_id(self):
        """Test that a valid key returns the agent_id."""
        from app.domain.aggregates.api_key import APIKeyAggregate

        aggregate = APIKeyAggregate(agent_id="agent-123")
        aggregate.create(key_id="key123", key_hash="stored_hash")

        request = MagicMock()
        request.headers = {"X-API-Key": "key123.plain_key"}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        repo = AsyncMock()
        repo.get_key_hash = AsyncMock(return_value=("agent-123", "stored_hash"))
        repo.load_agent_keys = AsyncMock(return_value=aggregate)
        repo.save = AsyncMock()

        with patch("app.core.auth.verify_api_key", return_value=True):
            agent_id = await validate_api_key(request, repo=repo)

        assert agent_id == "agent-123"
        assert request.state.agent_id == "agent-123"
        repo.save.assert_awaited_once()
