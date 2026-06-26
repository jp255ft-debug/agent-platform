"""API Key aggregate for agent authentication."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.domain.events.api_key_events import (
    APIKeyCreated,
    APIKeyExpired,
    APIKeyRevoked,
    APIKeyUsed,
)
from app.domain.events.base import DomainEvent


@dataclass
class APIKeyAggregate:
    """Manages API keys for an agent using event sourcing."""

    agent_id: str
    keys: list[APIKey] = field(default_factory=list)
    version: int = 0
    _changes: list[DomainEvent] = field(default_factory=list, repr=False)

    def create(self, key_id: str, key_hash: str, expires_in_days: int = 90) -> APIKeyAggregate:
        """Creates a new API key for this agent."""
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        event = APIKeyCreated(
            aggregate_id=self.agent_id,
            data={
                "key_id": key_id,
                "key_hash": key_hash,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._apply(event)
        self._changes.append(event)
        return self

    def revoke_key(self, key_id: str, reason: str = "manual") -> None:
        """Revoke an API key."""
        event = APIKeyRevoked(
            aggregate_id=self.agent_id,
            data={
                "key_id": key_id,
                "reason": reason,
                "revoked_at": datetime.now(UTC).isoformat(),
            },
        )
        self._apply(event)
        self._changes.append(event)

    def rotate_key(self, old_key_id: str, new_key_id: str, new_key_hash: str, expires_in_days: int = 90) -> None:
        """Rotate API key: revoke old, create new."""
        self.revoke_key(old_key_id, reason="rotation")
        event = APIKeyCreated(
            aggregate_id=self.agent_id,
            data={
                "key_id": new_key_id,
                "key_hash": new_key_hash,
                "expires_at": (datetime.now(UTC) + timedelta(days=expires_in_days)).isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._apply(event)
        self._changes.append(event)

    def expire_keys(self) -> None:
        """Mark all expired keys as expired (called by scheduled job)."""
        now = datetime.now(UTC)
        for key in self.keys:
            if key.expires_at < now and not key.revoked and not key.expired:
                event = APIKeyExpired(
                    aggregate_id=self.agent_id,
                    data={"key_id": key.key_id, "expired_at": now.isoformat()},
                )
                self._apply(event)
                self._changes.append(event)

    def record_usage(self, key_id: str, ip_address: Optional[str] = None) -> None:
        """Record API key usage for audit trail."""
        event = APIKeyUsed(
            aggregate_id=self.agent_id,
            data={
                "key_id": key_id,
                "used_at": datetime.now(UTC).isoformat(),
                "ip_address": ip_address or "unknown",
            },
        )
        self._apply(event)
        self._changes.append(event)

    def _apply(self, event: DomainEvent) -> None:
        """Rebuild state from event."""
        if isinstance(event, APIKeyCreated):
            self.keys.append(
                APIKey(
                    key_id=event.data["key_id"],
                    key_hash=event.data["key_hash"],
                    expires_at=datetime.fromisoformat(event.data["expires_at"]),
                    created_at=datetime.fromisoformat(event.data["created_at"]),
                )
            )
        elif isinstance(event, APIKeyRevoked):
            for key in self.keys:
                if key.key_id == event.data["key_id"]:
                    key.revoked = True
                    key.revoked_at = datetime.fromisoformat(event.data["revoked_at"])
                    break
        elif isinstance(event, APIKeyExpired):
            for key in self.keys:
                if key.key_id == event.data["key_id"]:
                    key.expired = True
                    break
        elif isinstance(event, APIKeyUsed):
            for key in self.keys:
                if key.key_id == event.data["key_id"]:
                    key.last_used_at = datetime.fromisoformat(event.data["used_at"])
                    key.usage_count += 1
                    break
        self.version += 1

    def get_changes(self) -> list[DomainEvent]:
        """Return pending events and clear."""
        changes = self._changes.copy()
        self._changes.clear()
        return changes

    def is_valid(self, key_hash: str) -> bool:
        """Check if a given key hash is valid (exists, not revoked, not expired)."""
        now = datetime.now(UTC)
        for key in self.keys:
            if key.key_hash == key_hash and not key.revoked and not key.expired and key.expires_at > now:
                return True
        return False

    def active_keys(self) -> list[APIKey]:
        """Return non-revoked, non-expired keys."""
        now = datetime.now(UTC)
        return [k for k in self.keys if not k.revoked and not k.expired and k.expires_at > now]


@dataclass
class APIKey:
    """Value object representing an API key."""

    key_id: str
    key_hash: str
    expires_at: datetime
    created_at: datetime
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    expired: bool = False
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
