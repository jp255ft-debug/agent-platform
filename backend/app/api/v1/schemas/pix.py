"""Pydantic schemas for Pix payment endpoints.

Based on BUILD_GUIDE.md §16 — Camada 11: Integração com Sistema Financeiro Brasileiro.
"""
from typing import Optional

from pydantic import BaseModel, Field


class PixQRCodeRequest(BaseModel):
    """Request schema for generating a dynamic Pix QR Code."""

    amount: float = Field(..., gt=0, description="Amount in BRL (e.g., 10.50)")
    description: str = Field(
        ..., min_length=1, max_length=100,
        description="Payment description visible to payer",
    )
    payer_name: str = Field(
        ..., min_length=1, max_length=50,
        description="Name of the person/entity making the payment",
    )
    payer_document: Optional[str] = Field(
        None, max_length=18,
        description="CPF (###.###.###-##) or CNPJ (##.###.###/####-##) of payer",
    )
    agent_id: Optional[str] = Field(
        None, description="Agent ID to associate with this payment",
    )
    expires_in: int = Field(
        default=3600, ge=300, le=86400,
        description="QR Code expiration in seconds (min: 300, max: 86400)",
    )


class PixQRCodeResponse(BaseModel):
    """Response schema for QR Code generation."""

    qr_code_id: str = Field(..., description="Unique QR Code identifier")
    qr_code: str = Field(..., description="Base64-encoded QR Code image")
    qr_code_text: str = Field(..., description="Pix copy-paste code (BR Code)")
    amount: float = Field(..., description="Amount in BRL")
    status: str = Field(..., description="QR Code status (created/paid/expired)")
    expires_in: int = Field(..., description="Expiration time in seconds")


class PixStatusResponse(BaseModel):
    """Response schema for payment status check."""

    qr_code_id: str = Field(..., description="QR Code identifier")
    status: str = Field(..., description="Payment status (created/paid/expired/canceled)")
    amount: float = Field(..., description="Original amount in BRL")
    paid_amount: Optional[float] = Field(None, description="Amount actually paid")
    paid_at: Optional[str] = Field(None, description="Timestamp of payment")
    payer_name: Optional[str] = Field(None, description="Name of the payer")


class PixWebhookEvent(BaseModel):
    """Schema for Stark Bank webhook events.

    Reference: https://starkbank.com/docs/api#webhook-event
    """

    id: str = Field(..., description="Event ID")
    status: str = Field(..., description="Event status (created/paid/expired)")
    amount: float = Field(..., description="Amount in BRL")
    agent_id: Optional[str] = Field(None, description="Associated agent ID")
    payer_name: Optional[str] = Field(None, description="Payer name")
    payer_document: Optional[str] = Field(None, description="Payer CPF/CNPJ")
    paid_at: Optional[str] = Field(None, description="Payment timestamp")
    created: Optional[str] = Field(None, description="Event creation timestamp")
    signature: Optional[str] = Field(None, description="HMAC signature for verification")
