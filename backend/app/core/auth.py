"""Authentication dependencies and utilities.

Provides API key authentication using X-API-Key header with format:
    X-API-Key: <key_id>.<plain_key>

Integrates with:
    - AgentPlatformError hierarchy for standardized error responses
    - Event sourcing via APIKeyAggregate
    - Redis cache for fast key lookup
    - Rate limiting via existing RateLimiter service
"""
from __future__ import annotations

import secrets

import bcrypt
from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

# Lazy imports to avoid circular dependencies during test collection
from app.core.dependencies import get_db_session, get_redis
from app.core.exceptions import (
    AuthenticationError,
)
from app.infrastructure.db.repositories.api_key_repository import APIKeyRepository


def hash_api_key(plain_key: str) -> str:
    """Hash an API key using bcrypt (for storage)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_key.encode("utf-8"), salt).decode("utf-8")


def verify_api_key(plain_key: str, hashed: str) -> bool:
    """Verify a plain key against its stored hash."""
    return bcrypt.checkpw(plain_key.encode("utf-8"), hashed.encode("utf-8"))


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key pair (plain, hash).

    Returns:
        Tuple of (plain_key, hashed_key). The plain key should be shown
        to the user only once. The hash is stored in the database.
    """
    plain = secrets.token_urlsafe(32)
    hashed = hash_api_key(plain)
    return plain, hashed


async def get_api_key_repository(
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> APIKeyRepository:
    """Dependency: returns API key repository with Redis cache."""
    return APIKeyRepository(db=db, redis=redis)


async def validate_api_key(
    request: Request,
    api_key_header: str | None = None,
    repo: APIKeyRepository = Depends(get_api_key_repository),
) -> str | None:
    """
    Dependency: validates X-API-Key header and returns agent_id.

    Expects header format: X-API-Key: <key_id>.<plain_key>

    Returns:
        agent_id of the authenticated agent, or None if no key provided.
        (Callers should handle None for bootstrap scenarios.)

    Raises:
        AuthenticationError: if key provided but invalid format, not found, or revoked.
    """
    # Extract from header
    api_key = api_key_header or request.headers.get("X-API-Key")
    if not api_key:
        return None  # No key provided — caller decides if this is allowed

    # Parse key_id.plain_key format
    if "." not in api_key:
        raise AuthenticationError(
            message="Invalid API key format",
            details={"expected": "key_id.plain_key"},
        )

    key_id, plain_key = api_key.split(".", 1)

    # Retrieve stored hash for this key_id
    agent_id, stored_hash = await repo.get_key_hash(key_id)
    if not agent_id:
        raise AuthenticationError(
            message="API key not found",
            details={"key_id": key_id},
        )

    # Verify the plain key against stored hash
    if not verify_api_key(plain_key, stored_hash):
        raise AuthenticationError(message="Invalid API key")

    # Load aggregate to check key validity (non-expired, non-revoked)
    aggregate = await repo.load_agent_keys(agent_id)
    if not aggregate.is_valid(stored_hash):
        raise AuthenticationError(
            message="API key revoked or expired",
            details={"agent_id": agent_id},
        )

    # Record usage for audit trail
    aggregate.record_usage(key_id, ip_address=request.client.host if request.client else None)
    await repo.save(aggregate)

    # Store agent_id in request state for downstream use
    request.state.agent_id = agent_id
    return agent_id


async def get_current_agent(agent_id: str | None = Depends(validate_api_key)) -> str | None:
    """Simple alias: returns agent_id of authenticated agent."""
    return agent_id
