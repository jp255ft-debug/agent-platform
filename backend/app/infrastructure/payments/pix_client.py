"""Pix integration client (Stark Bank).

Integrates with Stark Bank API for Pix payment processing:
- Dynamic QR Code generation
- Payment status checking
- Webhook event handling

Based on BUILD_GUIDE.md §16 — Camada 11: Integração com Sistema Financeiro Brasileiro.

Environment variables:
    STARK_BANK_API_KEY: Stark Bank API key (sandbox or production)
    STARK_BANK_ENVIRONMENT: "sandbox" (default) or "production"
    STARK_BANK_WEBHOOK_URL: URL for Pix payment webhooks
"""
from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.exceptions import PixError


class PixClientError(PixError):
    """Base exception for Pix client errors."""


class PixClient:
    """Client for Stark Bank Pix API.

    Handles dynamic QR Code generation and payment verification.
    Follows the same pattern as other infrastructure clients (Web3Client, etc.).
    """

    BASE_URLS = {
        "sandbox": "https://sandbox.api.starkbank.com/v2",
        "production": "https://api.starkbank.com/v2",
    }

    def __init__(
        self,
        api_key: str | None = None,
        environment: str | None = None,
        webhook_url: str | None = None,
    ):
        """Initialize Pix client.

        Args:
            api_key: Stark Bank API key. Defaults to STARK_BANK_API_KEY env var.
            environment: "sandbox" or "production". Defaults to STARK_BANK_ENVIRONMENT.
            webhook_url: URL for Pix webhook callbacks.
        """
        self._api_key = api_key or getattr(settings, "STARK_BANK_API_KEY", "")
        self._environment = environment or getattr(settings, "STARK_BANK_ENVIRONMENT", "sandbox")
        self._webhook_url = webhook_url or getattr(settings, "STARK_BANK_WEBHOOK_URL", "")

        base_url = self.BASE_URLS.get(self._environment)
        if not base_url:
            raise PixClientError(f"Invalid environment: {self._environment}. Use 'sandbox' or 'production'.")

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AgentPlatform/0.1.0",
            },
            timeout=30.0,
        )

    async def create_qr_code(
        self,
        amount: Decimal,
        description: str,
        payer_name: str,
        payer_document: str | None = None,
        expires_in: int = 3600,
    ) -> dict:
        """Generate a dynamic Pix QR Code.

        Args:
            amount: Transaction amount in BRL (e.g., Decimal("10.50")).
            description: Payment description visible to payer.
            payer_name: Name of the person/entity making the payment.
            payer_document: Optional CPF/CNPJ of payer.
            expires_in: QR Code expiration in seconds (default: 1 hour).

        Returns:
            dict with keys:
                - id: QR Code identifier
                - qr_code: Base64-encoded QR Code image
                - qr_code_text: Pix copy-paste code (BR Code)
                - url: QR Code URL
                - status: "created" | "paid" | "expired"

        Raises:
            PixClientError: On API failure or invalid parameters.
        """
        if amount <= Decimal("0"):
            raise PixClientError("Amount must be greater than zero.")

        payload = {
            "amount": int(amount * 100),  # Convert BRL to cents
            "description": description[:100],  # Max 100 chars
            "payer_name": payer_name[:50],  # Max 50 chars
            "expires_in": min(expires_in, 86400),  # Max 24 hours
        }

        if payer_document:
            payload["payer_document"] = payer_document

        if self._webhook_url:
            payload["webhook_url"] = self._webhook_url

        try:
            response = await self._client.post("/dynamic-brcode", json=payload)
            response.raise_for_status()
            data = response.json()

            return {
                "id": data.get("id"),
                "qr_code": data.get("brcode", ""),
                "qr_code_text": data.get("brcode", ""),
                "url": data.get("url", ""),
                "status": data.get("status", "created"),
                "amount": amount,
                "created_at": data.get("created"),
            }

        except httpx.HTTPStatusError as e:
            raise PixClientError(
                f"Stark Bank API error: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise PixClientError(f"Request failed: {str(e)}") from e

    async def check_payment(self, qr_code_id: str) -> dict:
        """Check the status of a Pix payment.

        Args:
            qr_code_id: QR Code identifier returned by create_qr_code().

        Returns:
            dict with keys:
                - id: QR Code identifier
                - status: "created" | "paid" | "expired" | "canceled"
                - amount: Original amount in BRL
                - paid_amount: Amount actually paid (if paid)
                - paid_at: Timestamp of payment (if paid)
                - payer: Payer info (if paid)

        Raises:
            PixClientError: On API failure.
        """
        if not qr_code_id:
            raise PixClientError("qr_code_id is required.")

        try:
            response = await self._client.get(f"/dynamic-brcode/{qr_code_id}")
            response.raise_for_status()
            data = response.json()

            result = {
                "id": data.get("id"),
                "status": data.get("status", "unknown"),
                "amount": Decimal(str(data.get("amount", 0))) / 100,
            }

            if data.get("status") == "paid":
                result["paid_amount"] = Decimal(str(data.get("amount", 0))) / 100
                result["paid_at"] = data.get("paid_at")
                result["payer"] = {
                    "name": data.get("payer_name"),
                    "document": data.get("payer_document"),
                }

            return result

        except httpx.HTTPStatusError as e:
            raise PixClientError(
                f"Stark Bank API error: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise PixClientError(f"Request failed: {str(e)}") from e

    async def list_transactions(
        self,
        limit: int = 10,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
    ) -> list:
        """List Pix transactions.

        Args:
            limit: Max number of transactions (max 100).
            after: Filter by creation date (ISO format).
            before: Filter by creation date (ISO format).
            status: Filter by status ("created", "paid", "expired", "canceled").

        Returns:
            List of transaction dicts.

        Raises:
            PixClientError: On API failure.
        """
        params = {"limit": min(limit, 100)}

        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if status:
            params["status"] = status

        try:
            response = await self._client.get("/dynamic-brcode", params=params)
            response.raise_for_status()
            data = response.json()

            transactions = []
            for item in data.get("brcodes", []):
                transactions.append({
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "amount": Decimal(str(item.get("amount", 0))) / 100,
                    "created_at": item.get("created"),
                    "paid_at": item.get("paid_at"),
                    "payer_name": item.get("payer_name"),
                })

            return transactions

        except httpx.HTTPStatusError as e:
            raise PixClientError(
                f"Stark Bank API error: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise PixClientError(f"Request failed: {str(e)}") from e

    async def close(self) -> None:
        """Close the HTTP client session."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
