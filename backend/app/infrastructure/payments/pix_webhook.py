"""Pix webhook handler for Stark Bank payment confirmations.

Based on BUILD_GUIDE.md §16 — Camada 11: Integração com Sistema Financeiro Brasileiro.

Handles incoming webhook events from Stark Bank when Pix payments are confirmed.
Validates HMAC signatures and creates domain events in the Event Store.
"""
import hashlib
import hmac
import logging
from typing import Optional

from app.core.config import settings
from app.domain.events.payment_events import PixPaymentReceived

logger = logging.getLogger(__name__)


class PixWebhookHandler:
    """Handles Stark Bank webhook events for Pix payment confirmations.

    In production, validates the HMAC-SHA256 signature sent in the
    X-Signature header against the webhook secret configured in Stark Bank.
    """

    def __init__(self, webhook_secret: Optional[str] = None):
        """Initialize webhook handler.

        Args:
            webhook_secret: Stark Bank webhook secret for HMAC validation.
                Defaults to STARK_BANK_WEBHOOK_SECRET env var.
        """
        self._webhook_secret = webhook_secret or getattr(
            settings, "STARK_BANK_WEBHOOK_SECRET", ""
        )

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """Validate HMAC-SHA256 signature from Stark Bank.

        Args:
            payload: Raw request body as bytes.
            signature: HMAC signature from X-Signature header.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self._webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature validation")
            return True

        if not signature:
            logger.error("Missing X-Signature header")
            return False

        expected = hmac.new(
            self._webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature.lower())

    def process_event(self, event_data: dict) -> Optional[PixPaymentReceived]:
        """Process a Stark Bank webhook event.

        Args:
            event_data: Parsed webhook event data from Stark Bank.

        Returns:
            PixPaymentReceived domain event if payment is confirmed,
            None if event should be ignored.
        """
        event_type = event_data.get("type", "")
        event_id = event_data.get("id", "")

        logger.debug("Processing webhook event: type=%s, id=%s", event_type, event_id)

        # Only process payment confirmation events
        if event_type != "payment.confirmed":
            logger.debug("Ignoring event type: %s", event_type)
            return None

        # Extract payment details from event payload
        payment = event_data.get("payment", {})
        amount = payment.get("amount", 0)
        status = payment.get("status", "")

        if status != "paid":
            logger.debug("Ignoring non-paid payment: status=%s", status)
            return None

        # Create domain event
        domain_event = PixPaymentReceived(
            payment_id=event_id,
            qr_code_id=payment.get("brcode_id", event_id),
            agent_id=payment.get("metadata", {}).get("agent_id", "unknown"),
            amount_brl=float(amount) / 100 if amount else 0.0,
            payer_name=payment.get("payer_name", "unknown"),
            payer_document=payment.get("payer_document", "unknown"),
            paid_at=payment.get("paid_at", ""),
        )

        logger.info(
            "Pix payment confirmed: id=%s, amount=%.2f, payer=%s",
            event_id, domain_event.data["amount_brl"], domain_event.data["payer_name"],
        )

        return domain_event
