"""Unit tests for error handler middleware."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.middleware.error_handler import (
    add_error_handlers,
    agent_platform_error_handler,
    unhandled_error_handler,
)
from app.core.exceptions import (
    AgentPlatformError,
    AgentNotFoundError,
    RateLimitExceededError,
    ValidationError,
)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/agents/test-123"
    return request


class TestAgentPlatformErrorHandler:
    """Test agent_platform_error_handler function."""

    async def test_returns_json_response(self, mock_request):
        exc = AgentNotFoundError(agent_id="test-123")

        response = await agent_platform_error_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

    async def test_returns_standardized_error_format(self, mock_request):
        exc = AgentNotFoundError(agent_id="test-123")

        response = await agent_platform_error_handler(mock_request, exc)
        body = response.body.decode()

        assert '"code":"AGENT_NOT_FOUND"' in body
        assert '"message":"Agent' in body
        assert '"details"' in body
        assert '"http_status":404' in body

    async def test_handles_rate_limit_error(self, mock_request):
        exc = RateLimitExceededError(agent_id="agent-456", resource_type="llm")

        response = await agent_platform_error_handler(mock_request, exc)

        assert response.status_code == 429
        body = response.body.decode()
        assert '"code":"RATE_LIMIT_EXCEEDED"' in body

    async def test_handles_validation_error(self, mock_request):
        exc = ValidationError("Invalid input", field="agent_id")

        response = await agent_platform_error_handler(mock_request, exc)

        assert response.status_code == 422
        body = response.body.decode()
        assert '"code":"VALIDATION_ERROR"' in body
        assert '"field":"agent_id"' in body

    async def test_handles_generic_platform_error(self, mock_request):
        exc = AgentPlatformError(
            message="Something went wrong",
            code="CUSTOM_ERROR",
            http_status=400,
            details={"reason": "test"},
        )

        response = await agent_platform_error_handler(mock_request, exc)

        assert response.status_code == 400
        body = response.body.decode()
        assert '"code":"CUSTOM_ERROR"' in body
        assert '"reason":"test"' in body


class TestUnhandledErrorHandler:
    """Test unhandled_error_handler function."""

    async def test_returns_500_json_response(self, mock_request):
        exc = Exception("Unexpected crash")

        response = await unhandled_error_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    async def test_returns_generic_error_message(self, mock_request):
        exc = Exception("Unexpected crash")

        response = await unhandled_error_handler(mock_request, exc)
        body = response.body.decode()

        assert '"code":"INTERNAL_SERVER_ERROR"' in body
        assert '"message":"An unexpected error occurred"' in body
        assert '"http_status":500' in body

    async def test_does_not_leak_exception_details(self, mock_request):
        exc = Exception("Secret DB credentials leaked!")

        response = await unhandled_error_handler(mock_request, exc)
        body = response.body.decode()

        assert "Secret DB credentials" not in body
        assert "An unexpected error occurred" in body


class TestAddErrorHandlers:
    """Test add_error_handlers function."""

    def test_registers_both_handlers(self):
        app = MagicMock(spec=FastAPI)

        add_error_handlers(app)

        assert app.add_exception_handler.call_count == 2
        # First call: AgentPlatformError
        assert app.add_exception_handler.call_args_list[0][0][0] == AgentPlatformError
        # Second call: Exception
        assert app.add_exception_handler.call_args_list[1][0][0] == Exception

    def test_registers_on_real_app(self):
        app = FastAPI()

        add_error_handlers(app)

        # Verify handlers are registered by checking exception handlers
        assert AgentPlatformError in app.exception_handlers
        assert Exception in app.exception_handlers
