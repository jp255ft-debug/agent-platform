"""Domain events for API key management."""
from app.domain.events.base import DomainEvent


class APIKeyCreated(DomainEvent):
    """Emitted when a new API key is created."""
    pass


class APIKeyRevoked(DomainEvent):
    """Emitted when an API key is revoked."""
    pass


class APIKeyExpired(DomainEvent):
    """Emitted when an API key expires."""
    pass


class APIKeyRotated(DomainEvent):
    """Emitted when an API key is rotated (revoke + create)."""
    pass


class APIKeyUsed(DomainEvent):
    """Emitted when an API key is successfully used for authentication."""
    pass
