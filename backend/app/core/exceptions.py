"""
Agent Platform — Hierarquia de Exceções Padronizada.

Fornece uma hierarquia completa de exceções com error codes,
permitindo rastreamento preciso de erros em toda a plataforma.

Uso:
    from app.core.exceptions import (
        AgentNotFoundError, PaymentVerificationError, RateLimitExceededError,
    )

    raise AgentNotFoundError(agent_id="abc-123")
    # → AgentNotFoundError: Agent 'abc-123' not found [code: AGENT_NOT_FOUND]

Estrutura:
    AgentPlatformError (base)
    ├── ConfigurationError
    ├── DomainError
    │   ├── AggregateNotFoundError
    │   ├── ConcurrencyError
    │   ├── InvalidEventError
    │   └── AgentNotFoundError
    ├── ValidationError
    ├── SecurityError
    │   ├── AuthenticationError
    │   ├── AuthorizationError
    │   └── InvalidSignatureError
    ├── PaymentError
    │   ├── InsufficientFundsError
    │   ├── PaymentVerificationError
    │   └── PixError
    ├── BlockchainError
    │   ├── DelegationError
    │   └── ContractNotConfiguredError
    ├── RateLimitExceededError
    ├── IdempotencyError
    ├── ComplianceError
    │   ├── KYCRequiredError
    │   └── AMLSanctionsError
    └── InfrastructureError
        ├── DatabaseError
        ├── CacheError
        └── MessagingError
"""

from typing import Any


class AgentPlatformError(Exception):
    """Base exception for all Agent Platform errors.

    All custom exceptions should inherit from this class.
    Provides a standardized error code and metadata dictionary.
    """

    code: str = "PLATFORM_ERROR"
    http_status: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        if code:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}
        self.message = message or self._default_message
        super().__init__(self._format_message())

    @property
    def _default_message(self) -> str:
        return f"An error occurred [{self.code}]"

    def _format_message(self) -> str:
        parts = [self.message]
        if self.details:
            parts.append(f"details={self.details}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to a dictionary for API responses."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "http_status": self.http_status,
            }
        }


# ─── Configuration ───────────────────────────────────────────────────────────


class ConfigurationError(AgentPlatformError):
    """Raised when system configuration is invalid or missing."""

    code = "CONFIGURATION_ERROR"
    http_status = 500


# ─── Domain ──────────────────────────────────────────────────────────────────


class DomainError(AgentPlatformError):
    """Base exception for domain-level errors."""

    code = "DOMAIN_ERROR"
    http_status = 400


class AggregateNotFoundError(DomainError):
    """Raised when an aggregate (event stream) is not found."""

    code = "AGGREGATE_NOT_FOUND"
    http_status = 404

    def __init__(self, aggregate_id: str, aggregate_type: str = "unknown"):
        super().__init__(
            message=f"{aggregate_type} '{aggregate_id}' not found",
            details={"aggregate_id": aggregate_id, "aggregate_type": aggregate_type},
        )


class ConcurrencyError(DomainError):
    """Raised when an optimistic concurrency conflict occurs."""

    code = "CONCURRENCY_CONFLICT"
    http_status = 409

    def __init__(self, aggregate_id: str, expected_version: int, actual_version: int):
        super().__init__(
            message=f"Concurrency conflict for '{aggregate_id}'",
            details={
                "aggregate_id": aggregate_id,
                "expected_version": expected_version,
                "actual_version": actual_version,
            },
        )


class InvalidEventError(DomainError):
    """Raised when an event is invalid or cannot be applied."""

    code = "INVALID_EVENT"

    def __init__(self, event_type: str, reason: str):
        super().__init__(
            message=f"Invalid event '{event_type}': {reason}",
            details={"event_type": event_type, "reason": reason},
        )


class AgentNotFoundError(DomainError):
    """Raised when an agent is not found."""

    code = "AGENT_NOT_FOUND"
    http_status = 404

    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent '{agent_id}' not found",
            details={"agent_id": agent_id},
        )


class AgentAlreadyExistsError(DomainError):
    """Raised when trying to register an agent that already exists."""

    code = "AGENT_ALREADY_EXISTS"
    http_status = 409

    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent '{agent_id}' already exists",
            details={"agent_id": agent_id},
        )


class InvoiceNotFoundError(DomainError):
    """Raised when an invoice is not found."""

    code = "INVOICE_NOT_FOUND"
    http_status = 404

    def __init__(self, invoice_id: str):
        super().__init__(
            message=f"Invoice '{invoice_id}' not found",
            details={"invoice_id": invoice_id},
        )


class InvoiceAlreadySettledError(DomainError):
    """Raised when trying to settle an already-settled invoice."""

    code = "INVOICE_ALREADY_SETTLED"
    http_status = 409

    def __init__(self, invoice_id: str, current_status: str):
        super().__init__(
            message=f"Invoice '{invoice_id}' is already '{current_status}'",
            details={"invoice_id": invoice_id, "current_status": current_status},
        )


class SessionNotFoundError(DomainError):
    """Raised when a billing session is not found."""

    code = "SESSION_NOT_FOUND"
    http_status = 404

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session '{session_id}' not found",
            details={"session_id": session_id},
        )


# ─── Validation ──────────────────────────────────────────────────────────────


class ValidationError(AgentPlatformError):
    """Raised when input validation fails."""

    code = "VALIDATION_ERROR"
    http_status = 422

    def __init__(self, message: str, *, field: str | None = None):
        details = {}
        if field:
            details["field"] = field
        super().__init__(message=message, details=details)


# ─── Security ────────────────────────────────────────────────────────────────


class SecurityError(AgentPlatformError):
    """Base exception for security-related errors."""

    code = "SECURITY_ERROR"
    http_status = 403


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""

    code = "AUTHENTICATION_FAILED"
    http_status = 401


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""

    code = "AUTHORIZATION_FAILED"
    http_status = 403


class InvalidSignatureError(SecurityError):
    """Raised when a cryptographic signature is invalid."""

    code = "INVALID_SIGNATURE"
    http_status = 401

    def __init__(self, message: str = "Invalid signature"):
        super().__init__(message=message)


# ─── Payments ────────────────────────────────────────────────────────────────


class PaymentError(AgentPlatformError):
    """Base exception for payment errors."""

    code = "PAYMENT_ERROR"
    http_status = 402


class InsufficientFundsError(PaymentError):
    """Raised when an agent has insufficient funds."""

    code = "INSUFFICIENT_FUNDS"

    def __init__(self, agent_id: str, required: float, available: float):
        super().__init__(
            message=f"Insufficient funds for agent '{agent_id}'",
            details={
                "agent_id": agent_id,
                "required": required,
                "available": available,
            },
        )


class PaymentVerificationError(PaymentError):
    """Raised when x402 payment verification fails."""

    code = "PAYMENT_VERIFICATION_FAILED"

    def __init__(self, reason: str, tx_hash: str | None = None):
        details = {"reason": reason}
        if tx_hash:
            details["tx_hash"] = tx_hash
        super().__init__(message=f"Payment verification failed: {reason}", details=details)


class PixError(PaymentError):
    """Raised when a Pix payment operation fails."""

    code = "PIX_ERROR"
    http_status = 502

    def __init__(self, message: str, *, upstream_status: int | None = None):
        details = {}
        if upstream_status:
            details["upstream_status"] = upstream_status
        super().__init__(message=message, details=details)


# ─── Blockchain ──────────────────────────────────────────────────────────────


class BlockchainError(AgentPlatformError):
    """Base exception for blockchain interaction errors."""

    code = "BLOCKCHAIN_ERROR"
    http_status = 502


class DelegationError(BlockchainError):
    """Raised when a delegation operation fails."""

    code = "DELEGATION_ERROR"

    def __init__(self, message: str, *, agent_address: str | None = None):
        details = {}
        if agent_address:
            details["agent_address"] = agent_address
        super().__init__(message=message, details=details)


class ContractNotConfiguredError(BlockchainError):
    """Raised when a smart contract address is not configured."""

    code = "CONTRACT_NOT_CONFIGURED"

    def __init__(self, contract_name: str):
        super().__init__(
            message=f"{contract_name} contract not configured",
            details={"contract_name": contract_name},
        )


class TransactionNotFoundError(BlockchainError):
    """Raised when a blockchain transaction is not found."""

    code = "TRANSACTION_NOT_FOUND"

    def __init__(self, tx_hash: str):
        super().__init__(
            message=f"Transaction '{tx_hash}' not found",
            details={"tx_hash": tx_hash},
        )


class TransactionFailedError(BlockchainError):
    """Raised when a blockchain transaction has failed status."""

    code = "TRANSACTION_FAILED"

    def __init__(self, tx_hash: str, status: int):
        super().__init__(
            message=f"Transaction '{tx_hash}' failed with status {status}",
            details={"tx_hash": tx_hash, "status": status},
        )


class SenderMismatchError(BlockchainError):
    """Raised when the transaction sender does not match the expected sender."""

    code = "SENDER_MISMATCH"

    def __init__(self, expected: str, actual: str):
        super().__init__(
            message="Transaction sender mismatch",
            details={"expected": expected, "actual": actual},
        )


class RecipientMismatchError(BlockchainError):
    """Raised when the transaction recipient does not match the expected recipient."""

    code = "RECIPIENT_MISMATCH"

    def __init__(self, expected: str, actual: str):
        super().__init__(
            message="Transaction recipient mismatch",
            details={"expected": expected, "actual": actual},
        )


class AmountMismatchError(BlockchainError):
    """Raised when the transaction amount does not match the expected amount."""

    code = "AMOUNT_MISMATCH"

    def __init__(self, expected: int, actual: int):
        super().__init__(
            message="Transaction amount mismatch",
            details={"expected": expected, "actual": actual},
        )


# ─── Rate Limiting ───────────────────────────────────────────────────────────


class RateLimitExceededError(AgentPlatformError):
    """Raised when rate limit is exceeded."""

    code = "RATE_LIMIT_EXCEEDED"
    http_status = 429

    def __init__(self, agent_id: str, resource_type: str):
        super().__init__(
            message=f"Rate limit exceeded for agent '{agent_id}' on '{resource_type}'",
            details={"agent_id": agent_id, "resource_type": resource_type},
        )


# ─── Idempotency ─────────────────────────────────────────────────────────────


class IdempotencyError(AgentPlatformError):
    """Raised when an idempotency conflict occurs."""

    code = "IDEMPOTENCY_CONFLICT"
    http_status = 409

    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"Request with idempotency key '{idempotency_key}' already processed",
            details={"idempotency_key": idempotency_key},
        )


# ─── Compliance ──────────────────────────────────────────────────────────────


class ComplianceError(AgentPlatformError):
    """Base exception for compliance-related errors."""

    code = "COMPLIANCE_ERROR"
    http_status = 403


class KYCRequiredError(ComplianceError):
    """Raised when KYC verification is required but incomplete."""

    code = "KYC_REQUIRED"

    def __init__(self, agent_id: str):
        super().__init__(
            message=f"KYC verification required for agent '{agent_id}'",
            details={"agent_id": agent_id},
        )


class AMLSanctionsError(ComplianceError):
    """Raised when AML screening detects a sanctioned entity."""

    code = "AML_SANCTIONS_HIT"

    def __init__(self, agent_id: str, reason: str):
        super().__init__(
            message=f"AML screening failed for agent '{agent_id}': {reason}",
            details={"agent_id": agent_id, "reason": reason},
        )


# ─── Infrastructure ──────────────────────────────────────────────────────────


class InfrastructureError(AgentPlatformError):
    """Base exception for infrastructure errors."""

    code = "INFRASTRUCTURE_ERROR"
    http_status = 503


class DatabaseError(InfrastructureError):
    """Raised when a database operation fails."""

    code = "DATABASE_ERROR"

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message=message)


class CacheError(InfrastructureError):
    """Raised when a cache operation fails."""

    code = "CACHE_ERROR"

    def __init__(self, message: str = "Cache operation failed"):
        super().__init__(message=message)


class MessagingError(InfrastructureError):
    """Raised when a messaging (Kafka) operation fails."""

    code = "MESSAGING_ERROR"

    def __init__(self, message: str = "Messaging operation failed"):
        super().__init__(message=message)
