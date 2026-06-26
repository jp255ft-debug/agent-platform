"""Unit tests for the consume resource endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.hgetall = AsyncMock(return_value={"tokens": "100", "last_refill": "1000000"})
    redis.eval = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_event_store():
    """Create a mock event store."""
    store = AsyncMock()
    store.load_stream = AsyncMock(return_value=[])
    store.append_events = AsyncMock()
    return store


@pytest.fixture
def consume_request_data():
    """Standard consume request data."""
    return {
        "agent_id": "agent-123",
        "resource_type": "compute",
        "amount": 10,
        "x402_payment": {"tx_hash": "0xabc", "amount": "100"},
        "idempotency_key": None,
    }


class TestConsumeResource:
    """Tests for POST /api/v1/consume"""

    @patch("app.api.v1.endpoints.consume._get_command_handlers")
    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    async def test_consume_success(
        self,
        mock_rate_limiter_cls,
        mock_idempotency_cls,
        mock_get_handlers,
        mock_db_session,
        mock_redis,
        consume_request_data,
    ):
        """Test successful resource consumption."""
        from app.api.v1.endpoints.consume import consume_resource
        from app.api.v1.schemas.consume import ConsumeRequest

        # Setup mocks
        mock_idempotency = AsyncMock()
        mock_idempotency.is_processed = AsyncMock(return_value=False)
        mock_idempotency_cls.return_value = mock_idempotency

        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit = AsyncMock(return_value=True)
        mock_limiter.get_remaining_tokens = AsyncMock(return_value=90)
        mock_rate_limiter_cls.return_value = mock_limiter

        mock_handlers = AsyncMock()
        mock_handlers.handle_consume_resource = AsyncMock(return_value="session-123")
        mock_get_handlers.return_value = mock_handlers

        body = ConsumeRequest(**consume_request_data)
        response = await consume_resource(body, mock_db_session, mock_redis)

        assert response.session_id == "session-123"
        assert response.total_consumed == 10
        assert response.remaining_tokens == 90
        assert response.status == "consumed"
        mock_handlers.handle_consume_resource.assert_awaited_once()

    @patch("app.api.v1.endpoints.consume._get_command_handlers")
    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    async def test_consume_idempotency_returns_cached(
        self,
        mock_rate_limiter_cls,
        mock_idempotency_cls,
        mock_get_handlers,
        mock_db_session,
        mock_redis,
        consume_request_data,
    ):
        """Test idempotency returns cached result."""
        from app.api.v1.endpoints.consume import consume_resource
        from app.api.v1.schemas.consume import ConsumeRequest

        consume_request_data["idempotency_key"] = "key-123"

        mock_idempotency = AsyncMock()
        mock_idempotency.is_processed = AsyncMock(return_value=True)
        mock_idempotency.get_result = AsyncMock(
            return_value="{'session_id': 'cached', 'total_consumed': 5, 'remaining_tokens': 95, 'status': 'consumed'}"
        )
        mock_idempotency_cls.return_value = mock_idempotency

        body = ConsumeRequest(**consume_request_data)
        response = await consume_resource(body, mock_db_session, mock_redis)

        assert response.session_id == "cached"
        assert response.total_consumed == 5
        mock_idempotency.is_processed.assert_awaited_once_with("key-123")

    @patch("app.api.v1.endpoints.consume._get_command_handlers")
    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    async def test_consume_idempotency_conflict(
        self,
        mock_rate_limiter_cls,
        mock_idempotency_cls,
        mock_get_handlers,
        mock_db_session,
        mock_redis,
        consume_request_data,
    ):
        """Test idempotency conflict raises 409."""
        from app.api.v1.endpoints.consume import consume_resource
        from app.api.v1.schemas.consume import ConsumeRequest

        consume_request_data["idempotency_key"] = "key-123"

        mock_idempotency = AsyncMock()
        mock_idempotency.is_processed = AsyncMock(return_value=True)
        mock_idempotency.get_result = AsyncMock(return_value=None)
        mock_idempotency_cls.return_value = mock_idempotency

        body = ConsumeRequest(**consume_request_data)
        with pytest.raises(HTTPException) as exc:
            await consume_resource(body, mock_db_session, mock_redis)
        assert exc.value.status_code == status.HTTP_409_CONFLICT

    @patch("app.api.v1.endpoints.consume._get_command_handlers")
    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    async def test_consume_rate_limit_exceeded(
        self,
        mock_rate_limiter_cls,
        mock_idempotency_cls,
        mock_get_handlers,
        mock_db_session,
        mock_redis,
        consume_request_data,
    ):
        """Test rate limit exceeded raises 429."""
        from app.api.v1.endpoints.consume import consume_resource
        from app.api.v1.schemas.consume import ConsumeRequest

        mock_idempotency = AsyncMock()
        mock_idempotency.is_processed = AsyncMock(return_value=False)
        mock_idempotency_cls.return_value = mock_idempotency

        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit = AsyncMock(return_value=False)
        mock_rate_limiter_cls.return_value = mock_limiter

        body = ConsumeRequest(**consume_request_data)
        with pytest.raises(HTTPException) as exc:
            await consume_resource(body, mock_db_session, mock_redis)
        assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @patch("app.api.v1.endpoints.consume._get_command_handlers")
    @patch("app.api.v1.endpoints.consume.IdempotencyService")
    @patch("app.api.v1.endpoints.consume.RateLimiter")
    async def test_consume_domain_error(
        self,
        mock_rate_limiter_cls,
        mock_idempotency_cls,
        mock_get_handlers,
        mock_db_session,
        mock_redis,
        consume_request_data,
    ):
        """Test domain error raises 402."""
        from app.api.v1.endpoints.consume import consume_resource
        from app.api.v1.schemas.consume import ConsumeRequest
        from app.core.exceptions import DomainError

        mock_idempotency = AsyncMock()
        mock_idempotency.is_processed = AsyncMock(return_value=False)
        mock_idempotency_cls.return_value = mock_idempotency

        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit = AsyncMock(return_value=True)
        mock_rate_limiter_cls.return_value = mock_limiter

        mock_handlers = AsyncMock()
        mock_handlers.handle_consume_resource = AsyncMock(
            side_effect=DomainError("Insufficient payment")
        )
        mock_get_handlers.return_value = mock_handlers

        body = ConsumeRequest(**consume_request_data)
        with pytest.raises(HTTPException) as exc:
            await consume_resource(body, mock_db_session, mock_redis)
        assert exc.value.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestGetBillingSession:
    """Tests for GET /api/v1/consume/sessions/{session_id}"""

    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    async def test_get_session_found(
        self, mock_event_store_cls, mock_db_session
    ):
        """Test getting a billing session that exists."""
        from app.api.v1.endpoints.consume import get_billing_session
        from app.domain.events.billing_events import BillingSessionStarted

        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(
            return_value=[
                BillingSessionStarted(
                    session_id="session-123",
                    agent_id="agent-123",
                    resource_type="compute",
                )
            ]
        )
        mock_event_store_cls.return_value = mock_store

        response = await get_billing_session("session-123", mock_db_session)
        assert response.session_id == "session-123"
        assert response.agent_id == "agent-123"
        assert response.resource_type == "compute"

    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    async def test_get_session_not_found(
        self, mock_event_store_cls, mock_db_session
    ):
        """Test getting a billing session that does not exist."""
        from app.api.v1.endpoints.consume import get_billing_session

        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(return_value=[])
        mock_event_store_cls.return_value = mock_store

        with pytest.raises(HTTPException) as exc:
            await get_billing_session("session-unknown", mock_db_session)
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


class TestGetCommandHandlers:
    """Tests for _get_command_handlers helper."""

    @patch("app.api.v1.endpoints.consume.PostgresEventStore")
    @patch("app.api.v1.endpoints.consume.CommandHandlers")
    def test_get_command_handlers(self, mock_handlers_cls, mock_store_cls, mock_db_session):
        """Test _get_command_handlers creates handlers correctly."""
        from app.api.v1.endpoints.consume import _get_command_handlers

        result = _get_command_handlers(mock_db_session)
        mock_store_cls.assert_called_once_with(mock_db_session)
        mock_handlers_cls.assert_called_once()
        assert result == mock_handlers_cls.return_value
