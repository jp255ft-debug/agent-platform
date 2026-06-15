"""Tests for the exception hierarchy.

Verifies that all exception classes:
1. Inherit correctly from AgentPlatformError
2. Have proper error codes
3. Have proper HTTP status codes
4. Serialize correctly via to_dict()
5. Include relevant details
"""
import pytest
from app.core.exceptions import (
    # Base
    AgentPlatformError,
    # Domain
    DomainError,
    AggregateNotFoundError,
    ConcurrencyError,
    InvalidEventError,
    AgentNotFoundError,
    AgentAlreadyExistsError,
    InvoiceNotFoundError,
    InvoiceAlreadySettledError,
    SessionNotFoundError,
    # Validation
    ValidationError,
    # Security
    SecurityError,
    AuthenticationError,
    AuthorizationError,
    InvalidSignatureError,
    # Payment
    PaymentError,
    InsufficientFundsError,
    PaymentVerificationError,
    PixError,
    # Blockchain
    BlockchainError,
    DelegationError,
    ContractNotConfiguredError,
    TransactionNotFoundError,
    TransactionFailedError,
    SenderMismatchError,
    RecipientMismatchError,
    AmountMismatchError,
    # Rate Limiting
    RateLimitExceededError,
    # Idempotency
    IdempotencyError,
    # Compliance
    ComplianceError,
    KYCRequiredError,
    AMLSanctionsError,
    # Infrastructure
    InfrastructureError,
    DatabaseError,
    CacheError,
    MessagingError,
    # Configuration
    ConfigurationError,
)


class TestExceptionHierarchy:
    """Verify the inheritance hierarchy is correct."""

    def test_base_exception(self):
        """AgentPlatformError is the root of all custom exceptions."""
        exc = AgentPlatformError("test error")
        assert exc.code == "PLATFORM_ERROR"
        assert exc.http_status == 500
        assert "test error" in str(exc)

    def test_base_to_dict(self):
        """to_dict() returns standardized error format."""
        exc = AgentPlatformError("test error", details={"key": "value"})
        result = exc.to_dict()
        assert result["error"]["code"] == "PLATFORM_ERROR"
        assert result["error"]["message"] == "test error"
        assert result["error"]["details"] == {"key": "value"}
        assert result["error"]["http_status"] == 500

    def test_domain_error_inheritance(self):
        """DomainError inherits from AgentPlatformError."""
        exc = DomainError()
        assert isinstance(exc, AgentPlatformError)
        assert exc.code == "DOMAIN_ERROR"
        assert exc.http_status == 400


class TestDomainExceptions:
    """Test domain-specific exceptions."""

    def test_aggregate_not_found(self):
        exc = AggregateNotFoundError(aggregate_id="agg-123", aggregate_type="Agent")
        assert exc.code == "AGGREGATE_NOT_FOUND"
        assert exc.http_status == 404
        assert "agg-123" in str(exc)
        assert exc.details["aggregate_id"] == "agg-123"

    def test_concurrency_error(self):
        exc = ConcurrencyError(aggregate_id="agg-1", expected_version=5, actual_version=7)
        assert exc.code == "CONCURRENCY_CONFLICT"
        assert exc.http_status == 409
        assert exc.details["expected_version"] == 5
        assert exc.details["actual_version"] == 7

    def test_invalid_event(self):
        exc = InvalidEventError(event_type="AgentRegistered", reason="Missing field")
        assert exc.code == "INVALID_EVENT"
        assert "AgentRegistered" in str(exc)

    def test_agent_not_found(self):
        exc = AgentNotFoundError(agent_id="agent-xyz")
        assert exc.code == "AGENT_NOT_FOUND"
        assert exc.http_status == 404
        assert exc.details["agent_id"] == "agent-xyz"

    def test_agent_already_exists(self):
        exc = AgentAlreadyExistsError(agent_id="agent-dup")
        assert exc.code == "AGENT_ALREADY_EXISTS"
        assert exc.http_status == 409

    def test_invoice_not_found(self):
        exc = InvoiceNotFoundError(invoice_id="inv-001")
        assert exc.code == "INVOICE_NOT_FOUND"
        assert exc.http_status == 404

    def test_invoice_already_settled(self):
        exc = InvoiceAlreadySettledError(invoice_id="inv-001", current_status="paid")
        assert exc.code == "INVOICE_ALREADY_SETTLED"
        assert exc.http_status == 409
        assert exc.details["current_status"] == "paid"

    def test_session_not_found(self):
        exc = SessionNotFoundError(session_id="sess-001")
        assert exc.code == "SESSION_NOT_FOUND"
        assert exc.http_status == 404


class TestValidationExceptions:
    """Test validation exceptions."""

    def test_validation_error(self):
        exc = ValidationError("Invalid CPF format", field="cpf")
        assert exc.code == "VALIDATION_ERROR"
        assert exc.http_status == 422
        assert exc.details["field"] == "cpf"

    def test_validation_error_no_field(self):
        exc = ValidationError("Generic validation error")
        assert exc.details == {}


class TestSecurityExceptions:
    """Test security exceptions."""

    def test_authentication_error(self):
        exc = AuthenticationError()
        assert exc.code == "AUTHENTICATION_FAILED"
        assert exc.http_status == 401

    def test_authorization_error(self):
        exc = AuthorizationError()
        assert exc.code == "AUTHORIZATION_FAILED"
        assert exc.http_status == 403

    def test_invalid_signature(self):
        exc = InvalidSignatureError()
        assert exc.code == "INVALID_SIGNATURE"
        assert exc.http_status == 401


class TestPaymentExceptions:
    """Test payment exceptions."""

    def test_insufficient_funds(self):
        exc = InsufficientFundsError(agent_id="agent-1", required=100.0, available=50.0)
        assert exc.code == "INSUFFICIENT_FUNDS"
        assert exc.http_status == 402
        assert exc.details["required"] == 100.0
        assert exc.details["available"] == 50.0

    def test_payment_verification_error(self):
        exc = PaymentVerificationError(reason="Invalid signature", tx_hash="0xabc")
        assert exc.code == "PAYMENT_VERIFICATION_FAILED"
        assert exc.details["tx_hash"] == "0xabc"
        assert exc.details["reason"] == "Invalid signature"

    def test_payment_verification_error_no_tx(self):
        exc = PaymentVerificationError(reason="Missing proof")
        assert "tx_hash" not in exc.details

    def test_pix_error(self):
        exc = PixError("Stark Bank API error", upstream_status=502)
        assert exc.code == "PIX_ERROR"
        assert exc.http_status == 502
        assert exc.details["upstream_status"] == 502


class TestBlockchainExceptions:
    """Test blockchain exceptions."""

    def test_delegation_error(self):
        exc = DelegationError("Failed to delegate", agent_address="0xabc")
        assert exc.code == "DELEGATION_ERROR"
        assert exc.http_status == 502
        assert exc.details["agent_address"] == "0xabc"

    def test_contract_not_configured(self):
        exc = ContractNotConfiguredError(contract_name="AgentDelegation")
        assert exc.code == "CONTRACT_NOT_CONFIGURED"
        assert "AgentDelegation" in str(exc)

    def test_transaction_not_found(self):
        exc = TransactionNotFoundError(tx_hash="0xdeadbeef")
        assert exc.code == "TRANSACTION_NOT_FOUND"
        assert exc.details["tx_hash"] == "0xdeadbeef"

    def test_transaction_failed(self):
        exc = TransactionFailedError(tx_hash="0xbad", status=0)
        assert exc.code == "TRANSACTION_FAILED"
        assert exc.details["status"] == 0

    def test_sender_mismatch(self):
        exc = SenderMismatchError(expected="0xa", actual="0xb")
        assert exc.code == "SENDER_MISMATCH"
        assert exc.details["expected"] == "0xa"

    def test_recipient_mismatch(self):
        exc = RecipientMismatchError(expected="0xa", actual="0xb")
        assert exc.code == "RECIPIENT_MISMATCH"

    def test_amount_mismatch(self):
        exc = AmountMismatchError(expected=1000, actual=500)
        assert exc.code == "AMOUNT_MISMATCH"
        assert exc.details["expected"] == 1000


class TestRateLimitExceptions:
    """Test rate limiting exceptions."""

    def test_rate_limit_exceeded(self):
        exc = RateLimitExceededError(agent_id="agent-1", resource_type="compute")
        assert exc.code == "RATE_LIMIT_EXCEEDED"
        assert exc.http_status == 429
        assert exc.details["agent_id"] == "agent-1"
        assert exc.details["resource_type"] == "compute"


class TestIdempotencyExceptions:
    """Test idempotency exceptions."""

    def test_idempotency_error(self):
        exc = IdempotencyError(idempotency_key="key-123")
        assert exc.code == "IDEMPOTENCY_CONFLICT"
        assert exc.http_status == 409
        assert exc.details["idempotency_key"] == "key-123"


class TestComplianceExceptions:
    """Test compliance exceptions."""

    def test_kyc_required(self):
        exc = KYCRequiredError(agent_id="agent-1")
        assert exc.code == "KYC_REQUIRED"
        assert exc.http_status == 403

    def test_aml_sanctions(self):
        exc = AMLSanctionsError(agent_id="agent-1", reason="OFAC match")
        assert exc.code == "AML_SANCTIONS_HIT"
        assert exc.details["reason"] == "OFAC match"


class TestInfrastructureExceptions:
    """Test infrastructure exceptions."""

    def test_database_error(self):
        exc = DatabaseError("Connection timeout")
        assert exc.code == "DATABASE_ERROR"
        assert exc.http_status == 503

    def test_cache_error(self):
        exc = CacheError()
        assert exc.code == "CACHE_ERROR"
        assert exc.http_status == 503

    def test_messaging_error(self):
        exc = MessagingError("Kafka unavailable")
        assert exc.code == "MESSAGING_ERROR"
        assert exc.http_status == 503


class TestConfigurationExceptions:
    """Test configuration exceptions."""

    def test_configuration_error(self):
        exc = ConfigurationError("Missing STARK_BANK_API_KEY")
        assert exc.code == "CONFIGURATION_ERROR"
        assert exc.http_status == 500


class TestExceptionSerialization:
    """Test that all exceptions serialize correctly."""

    @pytest.mark.parametrize("exc_factory, expected_code, expected_status", [
        (lambda: AgentNotFoundError("agent-1"), "AGENT_NOT_FOUND", 404),
        (lambda: ValidationError("bad input"), "VALIDATION_ERROR", 422),
        (lambda: AuthenticationError(), "AUTHENTICATION_FAILED", 401),
        (lambda: InsufficientFundsError("a", 10, 5), "INSUFFICIENT_FUNDS", 402),
        (lambda: RateLimitExceededError("a", "cpu"), "RATE_LIMIT_EXCEEDED", 429),
        (lambda: IdempotencyError("key-1"), "IDEMPOTENCY_CONFLICT", 409),
        (lambda: KYCRequiredError("a"), "KYC_REQUIRED", 403),
        (lambda: DatabaseError(), "DATABASE_ERROR", 503),
        (lambda: ConfigurationError("bad config"), "CONFIGURATION_ERROR", 500),
        (lambda: ContractNotConfiguredError("AgentDelegation"), "CONTRACT_NOT_CONFIGURED", 502),
        (lambda: PixError("API error"), "PIX_ERROR", 502),
    ])
    def test_to_dict_standard_format(self, exc_factory, expected_code, expected_status):
        """All exceptions produce the same JSON structure."""
        exc = exc_factory()
        result = exc.to_dict()

        assert "error" in result
        assert result["error"]["code"] == expected_code
        assert result["error"]["http_status"] == expected_status
        assert isinstance(result["error"]["message"], str)
        assert isinstance(result["error"]["details"], dict)

    def test_exception_is_raiseable(self):
        """All exceptions can be raised and caught as AgentPlatformError."""
        try:
            raise AgentNotFoundError(agent_id="test-agent")
        except AgentPlatformError as e:
            assert e.code == "AGENT_NOT_FOUND"
            assert e.http_status == 404

    def test_exception_chaining(self):
        """Exceptions support chaining with 'from'."""
        try:
            try:
                raise ValueError("original error")
            except ValueError as original:
                raise PixError("API error") from original
        except PixError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
