"""API endpoints for API key management (CRUD + rotation)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, status

from app.api.v1.schemas.api_keys import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyInfo,
    APIKeyListResponse,
    APIKeyRevokeRequest,
    APIKeyRotateResponse,
)
from app.core.auth import (
    generate_api_key,
    get_api_key_repository,
    validate_api_key,
)
from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.infrastructure.db.repositories.api_key_repository import APIKeyRepository

router = APIRouter(prefix="/api/v1/agents/{agent_id}/api-keys", tags=["api-keys"])


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    agent_id: str,
    request: APIKeyCreateRequest,
    repo: APIKeyRepository = Depends(get_api_key_repository),
    authenticated_agent: Optional[str] = Depends(validate_api_key),
    x_bootstrap_key: Optional[str] = Header(None),
):
    """Create a new API key for an agent.

    Authentication (choose one):
      1. Existing API key via X-API-Key header (standard)
      2. Bootstrap key via X-Bootstrap-Key header (development only)

    The plain_key is returned only once — store it securely.
    """
    # Bootstrap mode: allow creating first key without existing API key
    # Only works when APP_DEBUG=True (development/test environments)
    if authenticated_agent is None and x_bootstrap_key:
        if settings.APP_DEBUG:
            authenticated_agent = agent_id
        else:
            raise AuthenticationError(
                message="Bootstrap key not allowed in production",
                details={"hint": "Set APP_DEBUG=true in .env for development mode"},
            )

    if authenticated_agent is None:
        raise AuthenticationError(
            message="Missing authentication. Provide X-API-Key or X-Bootstrap-Key header.",
            details={"hint": "Use X-Bootstrap-Key: true for first key creation in development"},
        )

    # Ensure the authenticated agent matches or is admin
    if authenticated_agent != agent_id:
        raise AuthenticationError(
            message="Cannot create API key for another agent",
            details={"authenticated_agent": authenticated_agent, "target_agent": agent_id},
        )

    # Generate key pair
    key_id = str(uuid.uuid4())
    plain_key, hashed_key = generate_api_key()

    # Load aggregate and add key
    aggregate = await repo.load_agent_keys(agent_id)
    aggregate.create(key_id, hashed_key, expires_in_days=request.expires_in_days)
    # Note: request.label is available for future use (e.g., key metadata storage)
    await repo.save(aggregate)

    # Find the created key for expires_at
    created_key = next((k for k in aggregate.keys if k.key_id == key_id), None)
    expires_at = created_key.expires_at if created_key else datetime.now(timezone.utc)

    return APIKeyCreateResponse(
        key_id=key_id,
        plain_key=plain_key,
        expires_at=expires_at,
        agent_id=agent_id,
    )


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    agent_id: str,
    repo: APIKeyRepository = Depends(get_api_key_repository),
    authenticated_agent: Optional[str] = Depends(validate_api_key),
    x_bootstrap_key: Optional[str] = Header(None),
):
    """List all API keys for an agent (public info only, no plain keys).

    Authentication (choose one):
      1. Existing API key via X-API-Key header (standard)
      2. Bootstrap key via X-Bootstrap-Key header (development only)
    """
    # Bootstrap mode: allow listing keys without existing API key
    if authenticated_agent is None and x_bootstrap_key:
        if settings.APP_DEBUG:
            authenticated_agent = agent_id
        else:
            raise AuthenticationError(
                message="Bootstrap key not allowed in production",
                details={"hint": "Set APP_DEBUG=true in .env for development mode"},
            )

    if not authenticated_agent or authenticated_agent != agent_id:
        raise AuthenticationError(
            message="Cannot list API keys for another agent",
            details={"authenticated_agent": authenticated_agent, "target_agent": agent_id},
        )

    aggregate = await repo.load_agent_keys(agent_id)
    keys = [
        APIKeyInfo(
            key_id=k.key_id,
            created_at=k.created_at,
            expires_at=k.expires_at,
            revoked=k.revoked,
            revoked_at=k.revoked_at,
            expired=k.expired,
        )
        for k in aggregate.keys
    ]

    return APIKeyListResponse(agent_id=agent_id, keys=keys)


@router.post("/{key_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    agent_id: str,
    key_id: str,
    request: APIKeyRevokeRequest,
    repo: APIKeyRepository = Depends(get_api_key_repository),
    authenticated_agent: Optional[str] = Depends(validate_api_key),
    x_bootstrap_key: Optional[str] = Header(None),
):
    """Revoke an API key.

    Authentication (choose one):
      1. Existing API key via X-API-Key header (standard)
      2. Bootstrap key via X-Bootstrap-Key header (development only)
    """
    # Bootstrap mode: allow revoking keys without existing API key
    if authenticated_agent is None and x_bootstrap_key:
        if settings.APP_DEBUG:
            authenticated_agent = agent_id
        else:
            raise AuthenticationError(
                message="Bootstrap key not allowed in production",
                details={"hint": "Set APP_DEBUG=true in .env for development mode"},
            )

    if not authenticated_agent or authenticated_agent != agent_id:
        raise AuthenticationError(
            message="Cannot revoke API key for another agent",
            details={"authenticated_agent": authenticated_agent, "target_agent": agent_id},
        )

    aggregate = await repo.load_agent_keys(agent_id)
    aggregate.revoke_key(key_id, reason=request.reason)
    await repo.save(aggregate)

    return {"status": "revoked", "key_id": key_id, "reason": request.reason}


@router.post("/{key_id}/rotate", response_model=APIKeyRotateResponse)
async def rotate_api_key(
    agent_id: str,
    key_id: str,
    repo: APIKeyRepository = Depends(get_api_key_repository),
    authenticated_agent: Optional[str] = Depends(validate_api_key),
    x_bootstrap_key: Optional[str] = Header(None),
):
    """Rotate an API key: revoke old, create new.

    Authentication (choose one):
      1. Existing API key via X-API-Key header (standard)
      2. Bootstrap key via X-Bootstrap-Key header (development only)
    """
    # Bootstrap mode: allow rotating keys without existing API key
    if authenticated_agent is None and x_bootstrap_key:
        if settings.APP_DEBUG:
            authenticated_agent = agent_id
        else:
            raise AuthenticationError(
                message="Bootstrap key not allowed in production",
                details={"hint": "Set APP_DEBUG=true in .env for development mode"},
            )

    if not authenticated_agent or authenticated_agent != agent_id:
        raise AuthenticationError(
            message="Cannot rotate API key for another agent",
            details={"authenticated_agent": authenticated_agent, "target_agent": agent_id},
        )

    # Generate new key
    new_key_id = str(uuid.uuid4())
    plain_key, hashed_key = generate_api_key()

    # Load aggregate and rotate
    aggregate = await repo.load_agent_keys(agent_id)
    aggregate.rotate_key(key_id, new_key_id, hashed_key, expires_in_days=90)
    await repo.save(aggregate)

    # Find the new key for expires_at
    new_key = next((k for k in aggregate.keys if k.key_id == new_key_id), None)
    expires_at = new_key.expires_at if new_key else datetime.now(timezone.utc)

    return APIKeyRotateResponse(
        new_key_id=new_key_id,
        plain_key=plain_key,
        expires_at=expires_at,
        old_key_id=key_id,
    )
