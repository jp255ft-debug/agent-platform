"""Security middleware: security headers, correlation ID, request logging."""
import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response.

    Implements OWASP recommended headers:
    - HSTS: enforce HTTPS
    - X-Content-Type-Options: prevent MIME sniffing
    - X-Frame-Options: prevent clickjacking
    - CSP: restrict content sources
    - Referrer-Policy: limit referrer info
    - Permissions-Policy: restrict browser features
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Inject a correlation ID into request state and response headers.

    Uses X-Correlation-ID from request if provided, otherwise generates one.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with method, path, correlation_id, and status."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = getattr(request.state, "correlation_id", "N/A")
        agent_id = getattr(request.state, "agent_id", "anonymous")

        logger.info(
            "request_started method=%s path=%s correlation_id=%s agent_id=%s",
            request.method,
            request.url.path,
            correlation_id,
            agent_id,
        )

        response = await call_next(request)

        logger.info(
            "request_finished method=%s path=%s status=%d correlation_id=%s agent_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            correlation_id,
            agent_id,
        )

        return response
