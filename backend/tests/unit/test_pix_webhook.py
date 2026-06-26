"""Unit tests for PixWebhookHandler."""
import hashlib
import hmac
from unittest.mock import patch

import pytest

from app.infrastructure.payments.pix_webhook import PixWebhookHandler
from app.domain.events.payment_events import PixPaymentReceived


@pytest.fixture
def handler():
    """Create a PixWebhookHandler with a known secret."""
    return PixWebhookHandler(webhook_secret="test-secret")


@pytest.fixture
def handler_no_secret():
    """Create a PixWebhookHandler without a webhook secret."""
    return PixWebhookHandler(webhook_secret="")


def make_payment_confirmed_event(**overrides):
    """Create a payment.confirmed webhook event."""
    event = {
        "id": "evt-123",
        "type": "payment.confirmed",
        "payment": {
            "id": "pay-456",
            "brcode_id": "qr-789",
            "amount": 1050,
            "status": "paid",
            "payer_name": "John Doe",
            "payer_document": "123.456.789-00",
            "paid_at": "2026-06-20T22:05:00Z",
            "metadata": {"agent_id": "agent_123"},
        },
    }
    # Apply overrides at top level
    for key, value in overrides.items():
        if key in ("type", "id"):
            event[key] = value
        else:
            event["payment"][key] = value
    return event


class TestPixWebhookHandlerInitialization:
    """Test PixWebhookHandler initialization."""

    def test_init_with_secret(self):
        handler = PixWebhookHandler(webhook_secret="my-secret")
        assert handler._webhook_secret == "my-secret"

    def test_init_without_secret(self):
        handler = PixWebhookHandler(webhook_secret="")
        assert handler._webhook_secret == ""

    def test_init_defaults_to_settings(self):
        with patch("app.infrastructure.payments.pix_webhook.settings") as mock_settings:
            mock_settings.STARK_BANK_WEBHOOK_SECRET = "env-secret"
            handler = PixWebhookHandler()
            assert handler._webhook_secret == "env-secret"


class TestValidateSignature:
    """Test validate_signature method."""

    def test_valid_signature(self, handler):
        payload = b'{"test": "data"}'
        expected = hmac.new(
            b"test-secret", payload, hashlib.sha256
        ).hexdigest()

        result = handler.validate_signature(payload, expected)
        assert result is True

    def test_invalid_signature(self, handler):
        payload = b'{"test": "data"}'

        result = handler.validate_signature(payload, "invalid-signature")
        assert result is False

    def test_empty_signature(self, handler):
        payload = b'{"test": "data"}'

        result = handler.validate_signature(payload, "")
        assert result is False

    def test_no_secret_skips_validation(self, handler_no_secret):
        payload = b'{"test": "data"}'

        result = handler_no_secret.validate_signature(payload, "")
        assert result is True

    def test_signature_case_insensitive(self, handler):
        payload = b'{"test": "data"}'
        expected = hmac.new(
            b"test-secret", payload, hashlib.sha256
        ).hexdigest()

        # Test with uppercase signature
        result = handler.validate_signature(payload, expected.upper())
        assert result is True


class TestProcessEvent:
    """Test process_event method."""

    def test_payment_confirmed_event(self, handler):
        event = make_payment_confirmed_event()

        result = handler.process_event(event)

        assert result is not None
        assert isinstance(result, PixPaymentReceived)
        assert result.data["payment_id"] == "evt-123"
        assert result.data["qr_code_id"] == "qr-789"
        assert result.data["agent_id"] == "agent_123"
        assert result.data["amount_brl"] == 10.50
        assert result.data["payer_name"] == "John Doe"
        assert result.data["payer_document"] == "123.456.789-00"
        assert result.data["paid_at"] == "2026-06-20T22:05:00Z"

    def test_ignores_non_payment_event(self, handler):
        event = make_payment_confirmed_event(type="transfer.created")

        result = handler.process_event(event)
        assert result is None

    def test_ignores_non_paid_status(self, handler):
        event = make_payment_confirmed_event(status="created")

        result = handler.process_event(event)
        assert result is None

    def test_ignores_failed_payment(self, handler):
        event = make_payment_confirmed_event(status="failed")

        result = handler.process_event(event)
        assert result is None

    def test_missing_metadata_uses_unknown_agent(self, handler):
        event = make_payment_confirmed_event()
        del event["payment"]["metadata"]

        result = handler.process_event(event)

        assert result is not None
        assert result.data["agent_id"] == "unknown"

    def test_zero_amount(self, handler):
        event = make_payment_confirmed_event(amount=0)

        result = handler.process_event(event)

        assert result is not None
        assert result.data["amount_brl"] == 0.0

    def test_missing_payment_field(self, handler):
        event = {
            "id": "evt-123",
            "type": "payment.confirmed",
        }

        result = handler.process_event(event)

        # Without payment field, status defaults to "" which is != "paid", so returns None
        assert result is None

    def test_empty_event_data(self, handler):
        result = handler.process_event({})
        assert result is None
