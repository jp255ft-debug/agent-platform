"""Health check endpoint."""
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.health import HealthResponse
from app.core.config import settings
from app.core.dependencies import get_db_session, get_redis

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
):
    """Health check endpoint verifying database and cache connectivity."""
    services = {}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception:
        services["database"] = "unhealthy"

    # Check Redis
    try:
        await redis.ping()
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unhealthy"

    overall_status = "healthy" if all(s == "healthy" for s in services.values()) else "degraded"
    return HealthResponse(status=overall_status, version=settings.VERSION, services=services)
