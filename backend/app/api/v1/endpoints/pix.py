"""Pix payment endpoints.

Based on BUILD_GUIDE.md §16 — Camada 11: Integração com Sistema Financeiro Brasileiro.

Endpoints:
    POST /api/v1/pix/qrcode       — Generate dynamic Pix QR Code
    POST /api/v1/webhooks/pix     — Receive Pix payment confirmation webhook
    GET  /api/v1/pix/{id}/status  — Check Pix payment status
"""
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.api.v1.schemas.pix import (
    PixQRCodeRequest,
    PixQRCodeResponse,
    PixStatusResponse,
    PixWebhookEvent,
)
from app.domain.events.payment_events import PixPaymentReceived
from app.infrastructure.payments.pix_client import PixClient, PixClientError

logger = logging.getLogger(__name__)

router = APIRouter()


def get_pix_client() -> PixClient:
    """Factory for PixClient instance.

    Uses settings from environment variables configured in app.core.config.
    """
    from app.core.config import settings
    return PixClient(
        api_key=settings.STARK_BANK_API_KEY,
        environment=settings.STARK_BANK_ENVIRONMENT,
        webhook_url=settings.STARK_BANK_WEBHOOK_URL,
    )


@router.post("/qrcode", response_model=PixQRCodeResponse)
async def create_pix_qrcode(request: PixQRCodeRequest):
    """Generate a dynamic Pix QR Code for payment.

    The QR Code can be paid via any Pix-enabled bank app.
    After payment, a webhook will be sent to confirm the transaction.
    """
    client = get_pix_client()

    try:
        result = await client.create_qr_code(
            amount=Decimal(str(request.amount)),
            description=request.description,
            payer_name=request.payer_name,
            payer_document=request.payer_document,
            expires_in=request.expires_in,
        )

        return PixQRCodeResponse(
            qr_code_id=result["id"],
            qr_code=result["qr_code"],
            qr_code_text=result["qr_code_text"],
            amount=float(result["amount"]),
            status=result["status"],
            expires_in=request.expires_in,
        )

    except PixClientError as e:
        logger.error("Failed to create Pix QR Code: %s", str(e))
        raise HTTPException(status_code=502, detail=str(e))

    except Exception:
        logger.exception("Unexpected error creating Pix QR Code")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook")
async def pix_webhook(
    event: PixWebhookEvent,
    x_signature: Optional[str] = Header(None),
):
    """Receive Pix payment confirmation webhook from Stark Bank.

    This endpoint is called by Stark Bank when a Pix payment is confirmed.
    It creates a PixPaymentReceived event in the Event Store.

    Security: In production, validate the HMAC signature from the
    X-Signature header against the Stark Bank webhook secret.
    """
    # TODO: Validate HMAC signature in production
    # signature = x_signature
    # if not validate_hmac(event, signature):
    #     raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info(
        "Pix webhook received: id=%s, status=%s, amount=%.2f",
        event.id, event.status, event.amount,
    )

    if event.status != "paid":
        logger.debug("Ignoring non-paid webhook event: %s", event.status)
        return {"status": "ignored", "reason": f"Event status is '{event.status}', not 'paid'"}

    try:
        # Create domain event
        _domain_event = PixPaymentReceived(
            payment_id=event.id,
            qr_code_id=event.id,
            agent_id=event.agent_id or "unknown",
            amount_brl=event.amount,
            payer_name=event.payer_name or "unknown",
            payer_document=event.payer_document or "unknown",
            paid_at=event.paid_at or "",
        )

        # TODO: Persist event in Event Store (Semana 2)
        # await event_store.append_events(event.id, [domain_event], expected_version=0)

        # TODO: Publish to Kafka (Semana 2)
        # await kafka_producer.publish("payment.pix.received", domain_event.to_dict())

        logger.info(
            "Pix payment processed: payment_id=%s, amount=%.2f, payer=%s",
            event.id, event.amount, event.payer_name,
        )

        return {
            "status": "processed",
            "payment_id": event.id,
        }

    except Exception:
        logger.exception("Failed to process Pix webhook")
        raise HTTPException(status_code=500, detail="Failed to process payment")


@router.get("/{qr_code_id}/status", response_model=PixStatusResponse)
async def check_pix_status(qr_code_id: str):
    """Check the status of a Pix payment by QR Code ID."""
    client = get_pix_client()

    try:
        result = await client.check_payment(qr_code_id)

        return PixStatusResponse(
            qr_code_id=result["id"],
            status=result["status"],
            amount=float(result.get("amount", 0)),
            paid_amount=float(result.get("paid_amount", 0)) if "paid_amount" in result else None,
            paid_at=result.get("paid_at"),
            payer_name=result.get("payer", {}).get("name") if "payer" in result else None,
        )

    except PixClientError as e:
        logger.error("Failed to check Pix status: %s", str(e))
        raise HTTPException(status_code=502, detail=str(e))

    except Exception:
        logger.exception("Unexpected error checking Pix status")
        raise HTTPException(status_code=500, detail="Internal server error")
