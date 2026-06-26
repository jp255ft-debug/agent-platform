"""Pydantic schemas for API key management."""
from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key for an agent."""

    expires_in_days: int = Field(default=90, ge=1, le=365, description="Key expiration in days")
    label: str | None = Field(default="default", max_length=100, description="Optional label for the key")


class APIKeyCreateResponse(BaseModel):
    """Response after creating an API key.

    The plain_key is shown only once. Store it securely.
    """

    key_id: str = Field(..., description="Unique key identifier")
    plain_key: str = Field(..., description="Plain API key (show once)")
    expires_at: datetime = Field(..., description="Key expiration timestamp")
    agent_id: str = Field(..., description="Associated agent ID")


class APIKeyInfo(BaseModel):
    """Public information about an API key (no plain key)."""

    key_id: str = Field(..., description="Unique key identifier")
    created_at: datetime = Field(..., description="Key creation timestamp")
    expires_at: datetime = Field(..., description="Key expiration timestamp")
    revoked: bool = Field(default=False, description="Whether key is revoked")
    revoked_at: datetime | None = Field(default=None, description="Revocation timestamp")
    expired: bool = Field(default=False, description="Whether key is expired")


class APIKeyListResponse(BaseModel):
    """Response listing all API keys for an agent."""

    agent_id: str = Field(..., description="Agent ID")
    keys: list[APIKeyInfo] = Field(default_factory=list, description="List of API keys")


class APIKeyRevokeRequest(BaseModel):
    """Request to revoke an API key."""

    reason: str = Field(default="manual", description="Reason for revocation")


class APIKeyRotateResponse(BaseModel):
    """Response after rotating an API key."""

    new_key_id: str = Field(..., description="New key identifier")
    plain_key: str = Field(..., description="New plain API key (show once)")
    expires_at: datetime = Field(..., description="New key expiration timestamp")
    old_key_id: str = Field(..., description="Old key that was revoked")
