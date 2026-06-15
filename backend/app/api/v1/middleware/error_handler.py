"""
Error Handler Middleware — Padroniza respostas de erro da API.

Converte todas as exceções AgentPlatformError em respostas JSON
padronizadas com error code, mensagem e detalhes.

Uso:
    from app.api.v1.middleware.error_handler import add_error_handlers

    app = FastAPI()
    add_error_handlers(app)

    # Agora qualquer AgentPlatformError lançada em handlers/endpoints
    # será automaticamente convertida para:
    # {
    #   "error": {
    #     "code": "AGENT_NOT_FOUND",
    #     "message": "Agent 'abc-123' not found",
    #     "details": {"agent_id": "abc-123"},
    #     "http_status": 404
    #   }
    # }
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AgentPlatformError

logger = logging.getLogger(__name__)


async def agent_platform_error_handler(request: Request, exc: AgentPlatformError) -> JSONResponse:
    """Handle all AgentPlatformError exceptions with standardized JSON response."""
    error_dict = exc.to_dict()
    logger.warning(
        "API error: code=%s status=%d path=%s message=%s details=%s",
        exc.code,
        exc.http_status,
        request.url.path,
        exc.message,
        exc.details,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=error_dict,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a generic 500 response."""
    logger.exception(
        "Unhandled exception: path=%s error=%s",
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
                "http_status": 500,
            }
        },
    )


def add_error_handlers(app: FastAPI) -> None:
    """Register error handlers on a FastAPI application.

    Deve ser chamado durante a inicialização do app, antes de qualquer rota.

    Args:
        app: A instância do FastAPI application.
    """
    app.add_exception_handler(AgentPlatformError, agent_platform_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    logger.info("Error handlers registered: AgentPlatformError → JSON, Exception → 500")
