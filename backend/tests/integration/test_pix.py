"""Integration tests for Pix payment endpoints.

Tests:
    POST /api/v1/pix/qrcode — Generate dynamic Pix QR Code
    POST /api/v1/pix/webhook — Receive Pix payment confirmation webhook
    GET  /api/v1/pix/{qr_code_id}/status — Check Pix payment status
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestCreatePixQRCode:
    """Tests for POST /api/v1/pix/qrcode."""

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    def test_create_qrcode_success(self, mock_get_client, client: TestClient):
        """Should generate a Pix QR Code successfully."""
        mock_client = mock_get_client.return_value
        mock_client.create_qr_code = AsyncMock(return_value={
            "id": "qrcode-123",
            "qr_code": "base64-encoded-image",
            "qr_code_text": "000201010212...",
            "amount": 10.50,
            "status": "created",
        })

        response = client.post("/api/v1/pix/qrcode", json={
            "amount": 10.50,
            "description": "Payment for compute resources",
            "payer_name": "John Doe",
            "payer_document": "123.456.789-00",
            "expires_in": 3600,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["qr_code_id"] == "qrcode-123"
        assert data["qr_code"] == "base64-encoded-image"
        assert data["qr_code_text"] == "000201010212..."
        assert data["amount"] == 10.50
        assert data["status"] == "created"

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    def test_create_qrcode_pix_error(self, mock_get_client, client: TestClient):
        """Should return 502 when Pix API fails."""
        from app.infrastructure.payments.pix_client import PixClientError

        mock_client = mock_get_client.return_value
        mock_client.create_qr_code = AsyncMock(
            side_effect=PixClientError("Stark Bank API error: 400")
        )

        response = client.post("/api/v1/pix/qrcode", json={
            "amount": 10.50,
            "description": "Payment",
            "payer_name": "John Doe",
            "expires_in": 3600,
        })
        assert response.status_code == 502

    def test_create_qrcode_invalid_payload(self, client: TestClient):
        """Should return 422 for invalid payload."""
        response = client.post("/api/v1/pix/qrcode", json={
            "amount": -10,  # Invalid: must be > 0
            "description": "Payment",
            "payer_name": "John Doe",
            "expires_in": 3600,
        })
        assert response.status_code == 422

    def test_create_qrcode_missing_required(self, client: TestClient):
        """Should return 422 for missing required fields."""
        response = client.post("/api/v1/pix/qrcode", json={
            "amount": 10.50,
            # missing description, payer_name
        })
        assert response.status_code == 422


class TestPixWebhook:
    """Tests for POST /api/v1/pix/webhook."""

    def test_webhook_paid_success(self, client: TestClient):
        """Should process a paid webhook event successfully."""
        response = client.post("/api/v1/pix/webhook", json={
            "id": "event-123",
            "status": "paid",
            "amount": 100.00,
            "agent_id": "agent-123",
            "payer_name": "John Doe",
            "payer_document": "123.456.789-00",
            "paid_at": "2026-06-20T20:00:00Z",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["payment_id"] == "event-123"

    def test_webhook_non_paid_ignored(self, client: TestClient):
        """Should ignore non-paid webhook events."""
        response = client.post("/api/v1/pix/webhook", json={
            "id": "event-456",
            "status": "created",
            "amount": 100.00,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert "not 'paid'" in data["reason"]

    def test_webhook_expired_ignored(self, client: TestClient):
        """Should ignore expired webhook events."""
        response = client.post("/api/v1/pix/webhook", json={
            "id": "event-789",
            "status": "expired",
            "amount": 100.00,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"


class TestCheckPixStatus:
    """Tests for GET /api/v1/pix/{qr_code_id}/status."""

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    def test_check_status_paid(self, mock_get_client, client: TestClient):
        """Should return paid status."""
        mock_client = mock_get_client.return_value
        mock_client.check_payment = AsyncMock(return_value={
            "id": "qrcode-123",
            "status": "paid",
            "amount": 10.50,
            "paid_amount": 10.50,
            "paid_at": "2026-06-20T20:00:00Z",
            "payer": {"name": "John Doe", "document": "123.456.789-00"},
        })

        response = client.get("/api/v1/pix/qrcode-123/status")
        assert response.status_code == 200
        data = response.json()
        assert data["qr_code_id"] == "qrcode-123"
        assert data["status"] == "paid"
        assert data["paid_amount"] == 10.50
        assert data["payer_name"] == "John Doe"

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    def test_check_status_created(self, mock_get_client, client: TestClient):
        """Should return created status when not yet paid."""
        mock_client = mock_get_client.return_value
        mock_client.check_payment = AsyncMock(return_value={
            "id": "qrcode-456",
            "status": "created",
            "amount": 25.00,
        })

        response = client.get("/api/v1/pix/qrcode-456/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["paid_amount"] is None
        assert data["paid_at"] is None

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    def test_check_status_pix_error(self, mock_get_client, client: TestClient):
        """Should return 502 when Pix API fails."""
        from app.infrastructure.payments.pix_client import PixClientError

        mock_client = mock_get_client.return_value
        mock_client.check_payment = AsyncMock(
            side_effect=PixClientError("Stark Bank API error: 404")
        )

        response = client.get("/api/v1/pix/non-existent/status")
        assert response.status_code == 502
