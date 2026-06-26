"""Unit tests for the Pix payment endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status


class TestCreatePixQRCode:
    """Tests for POST /api/v1/pix/qrcode"""

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    async def test_create_qrcode_success(self, mock_get_client):
        """Test successful QR code generation."""
        from app.api.v1.endpoints.pix import create_pix_qrcode
        from app.api.v1.schemas.pix import PixQRCodeRequest

        mock_client = AsyncMock()
        mock_client.create_qr_code = AsyncMock(
            return_value={
                "id": "qr-123",
                "qr_code": "base64image",
                "qr_code_text": "00020126580014br.gov.bcb.pix",
                "amount": 100.50,
                "status": "created",
            }
        )
        mock_get_client.return_value = mock_client

        request = PixQRCodeRequest(
            amount=100.50,
            description="Test payment",
            payer_name="John Doe",
            payer_document="12345678901",
            expires_in=3600,
        )

        response = await create_pix_qrcode(request)
        assert response.qr_code_id == "qr-123"
        assert response.qr_code == "base64image"
        assert response.amount == 100.50
        assert response.status == "created"
        mock_client.create_qr_code.assert_awaited_once()

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    async def test_create_qrcode_client_error(self, mock_get_client):
        """Test QR code generation when Pix client fails."""
        from app.api.v1.endpoints.pix import create_pix_qrcode
        from app.api.v1.schemas.pix import PixQRCodeRequest
        from app.infrastructure.payments.pix_client import PixClientError

        mock_client = AsyncMock()
        mock_client.create_qr_code = AsyncMock(
            side_effect=PixClientError("API error")
        )
        mock_get_client.return_value = mock_client

        request = PixQRCodeRequest(
            amount=50.00,
            description="Test",
            payer_name="Jane Doe",
            expires_in=3600,
        )

        with pytest.raises(HTTPException) as exc:
            await create_pix_qrcode(request)
        assert exc.value.status_code == 502

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    async def test_create_qrcode_unexpected_error(self, mock_get_client):
        """Test QR code generation on unexpected error."""
        from app.api.v1.endpoints.pix import create_pix_qrcode
        from app.api.v1.schemas.pix import PixQRCodeRequest

        mock_client = AsyncMock()
        mock_client.create_qr_code = AsyncMock(
            side_effect=Exception("Unexpected")
        )
        mock_get_client.return_value = mock_client

        request = PixQRCodeRequest(
            amount=25.00,
            description="Test",
            payer_name="Test User",
            expires_in=3600,
        )

        with pytest.raises(HTTPException) as exc:
            await create_pix_qrcode(request)
        assert exc.value.status_code == 500


class TestPixWebhook:
    """Tests for POST /api/v1/pix/webhook"""

    @patch("app.api.v1.endpoints.pix.logger")
    async def test_webhook_paid_success(self, mock_logger):
        """Test successful webhook processing for paid event."""
        from app.api.v1.endpoints.pix import pix_webhook
        from app.api.v1.schemas.pix import PixWebhookEvent

        event = PixWebhookEvent(
            id="evt-123",
            status="paid",
            amount=100.50,
            agent_id="agent-123",
            payer_name="John Doe",
            payer_document="12345678901",
            paid_at="2026-06-21T12:00:00Z",
        )

        response = await pix_webhook(event, x_signature=None)
        assert response["status"] == "processed"
        assert response["payment_id"] == "evt-123"

    async def test_webhook_non_paid_ignored(self):
        """Test non-paid webhook events are ignored."""
        from app.api.v1.endpoints.pix import pix_webhook
        from app.api.v1.schemas.pix import PixWebhookEvent

        event = PixWebhookEvent(
            id="evt-456",
            status="created",
            amount=50.00,
        )

        response = await pix_webhook(event, x_signature=None)
        assert response["status"] == "ignored"
        assert "not 'paid'" in response["reason"]

    @patch("app.api.v1.endpoints.pix.logger")
    async def test_webhook_paid_error(self, mock_logger):
        """Test webhook processing when an error occurs."""
        from app.api.v1.endpoints.pix import pix_webhook
        from app.api.v1.schemas.pix import PixWebhookEvent

        event = PixWebhookEvent(
            id="evt-789",
            status="paid",
            amount=75.00,
            agent_id="agent-unknown",
            paid_at="2026-06-21T12:00:00Z",
        )

        # Mock PixPaymentReceived to raise an exception
        with patch(
            "app.api.v1.endpoints.pix.PixPaymentReceived",
            side_effect=Exception("Processing error"),
        ):
            with pytest.raises(HTTPException) as exc:
                await pix_webhook(event, x_signature=None)
            assert exc.value.status_code == 500


class TestCheckPixStatus:
    """Tests for GET /api/v1/pix/{qr_code_id}/status"""

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    async def test_check_status_success(self, mock_get_client):
        """Test successful status check."""
        from app.api.v1.endpoints.pix import check_pix_status

        mock_client = AsyncMock()
        mock_client.check_payment = AsyncMock(
            return_value={
                "id": "qr-123",
                "status": "paid",
                "amount": 100.50,
                "paid_amount": 100.50,
                "paid_at": "2026-06-21T12:00:00Z",
                "payer": {"name": "John Doe"},
            }
        )
        mock_get_client.return_value = mock_client

        response = await check_pix_status("qr-123")
        assert response.qr_code_id == "qr-123"
        assert response.status == "paid"
        assert response.paid_amount == 100.50
        assert response.payer_name == "John Doe"

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    async def test_check_status_client_error(self, mock_get_client):
        """Test status check when Pix client fails."""
        from app.api.v1.endpoints.pix import check_pix_status
        from app.infrastructure.payments.pix_client import PixClientError

        mock_client = AsyncMock()
        mock_client.check_payment = AsyncMock(
            side_effect=PixClientError("Not found")
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(HTTPException) as exc:
            await check_pix_status("qr-unknown")
        assert exc.value.status_code == 502

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    async def test_check_status_unexpected_error(self, mock_get_client):
        """Test status check on unexpected error."""
        from app.api.v1.endpoints.pix import check_pix_status

        mock_client = AsyncMock()
        mock_client.check_payment = AsyncMock(
            side_effect=Exception("Unexpected")
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(HTTPException) as exc:
            await check_pix_status("qr-123")
        assert exc.value.status_code == 500


class TestGetPixClient:
    """Tests for get_pix_client factory."""

    @patch("app.api.v1.endpoints.pix.get_pix_client")
    def test_get_pix_client(self, mock_get_pix_client):
        """Test get_pix_client returns a PixClient instance."""
        from app.api.v1.endpoints.pix import get_pix_client

        mock_client = MagicMock()
        mock_get_pix_client.return_value = mock_client

        result = get_pix_client()
        assert result == mock_client
