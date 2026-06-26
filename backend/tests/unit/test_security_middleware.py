"""Unit tests for security middleware."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, Response
from starlette.responses import JSONResponse

from app.api.v1.middleware.security import (
    SecurityHeadersMiddleware,
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
)


@pytest.fixture
def mock_app():
    """Create a mock ASGI app."""
    app = MagicMock()
    return app


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/v1/agents"
    request.headers = {}
    request.state = MagicMock()
    request.state.correlation_id = "test-correlation-id"
    request.state.agent_id = "agent-123"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""
    async def call_next(request):
        return JSONResponse(content={"status": "ok"}, status_code=200)
    return call_next


class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware."""

    @pytest.fixture
    def middleware(self, mock_app):
        return SecurityHeadersMiddleware(mock_app)

    async def test_adds_hsts_header(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    async def test_adds_x_content_type_options(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    async def test_adds_x_frame_options(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["X-Frame-Options"] == "DENY"

    async def test_adds_xss_protection(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    async def test_adds_csp_header(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["Content-Security-Policy"] == "default-src 'none'"

    async def test_adds_referrer_policy(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_adds_permissions_policy(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"

    async def test_all_seven_headers_present(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)
        expected_headers = [
            "Strict-Transport-Security",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
        ]
        for header in expected_headers:
            assert header in response.headers


class TestCorrelationIdMiddleware:
    """Test CorrelationIdMiddleware."""

    @pytest.fixture
    def middleware(self, mock_app):
        return CorrelationIdMiddleware(mock_app)

    async def test_generates_correlation_id_when_missing(self, middleware, mock_request, mock_call_next):
        mock_request.headers = {}
        mock_request.state = MagicMock()

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert hasattr(mock_request.state, "correlation_id")
        assert mock_request.state.correlation_id is not None
        assert "X-Correlation-ID" in response.headers

    async def test_uses_existing_correlation_id(self, middleware, mock_request, mock_call_next):
        mock_request.headers = {"X-Correlation-ID": "existing-id"}
        mock_request.state = MagicMock()

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.correlation_id == "existing-id"
        assert response.headers["X-Correlation-ID"] == "existing-id"

    async def test_correlation_id_in_response_headers(self, middleware, mock_request, mock_call_next):
        mock_request.headers = {"X-Correlation-ID": "req-123"}
        mock_request.state = MagicMock()

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-Correlation-ID"] == "req-123"


class TestRequestLoggingMiddleware:
    """Test RequestLoggingMiddleware."""

    @pytest.fixture
    def middleware(self, mock_app):
        return RequestLoggingMiddleware(mock_app)

    async def test_logs_request_and_response(self, middleware, mock_request, mock_call_next):
        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200

    async def test_handles_missing_correlation_id(self, middleware, mock_request, mock_call_next):
        mock_request.state = MagicMock(spec=[])  # Empty state
        # Remove correlation_id and agent_id attributes
        del mock_request.state.correlation_id
        del mock_request.state.agent_id

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200

    async def test_handles_missing_agent_id(self, middleware, mock_request, mock_call_next):
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "corr-123"
        del mock_request.state.agent_id

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 200
