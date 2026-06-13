class AgentPlatformError(Exception):
    """Base exception for the Agent Platform."""


class DomainError(AgentPlatformError):
    """Base exception for domain errors."""


class AggregateNotFoundError(DomainError):
    """Raised when an aggregate is not found."""


class ConcurrencyError(DomainError):
    """Raised when a concurrency conflict occurs."""


class InvalidEventError(DomainError):
    """Raised when an event is invalid."""


class RateLimitExceededError(AgentPlatformError):
    """Raised when rate limit is exceeded."""


class PaymentError(AgentPlatformError):
    """Base exception for payment errors."""


class InsufficientFundsError(PaymentError):
    """Raised when funds are insufficient."""


class InvalidSignatureError(PaymentError):
    """Raised when a signature is invalid."""


class DelegationError(AgentPlatformError):
    """Raised when a delegation error occurs."""


class IdempotencyError(AgentPlatformError):
    """Raised when an idempotency conflict occurs."""
