"""Unit tests for PixClient."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.infrastructure.payments.pix_client import PixClient, PixClientError


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def pix_client(mock_httpx_client):
    """Create a PixClient with mocked HTTP client."""
    with patch("app.infrastructure.payments.pix_client.httpx.AsyncClient", return_value=mock_httpx_client):
        with patch("app.infrastructure.payments.pix_client.settings") as mock_settings:
            mock_settings.STARK_BANK_API_KEY = "test-api-key"
            mock_settings.STARK_BANK_ENVIRONMENT = "sandbox"
            mock_settings.STARK_BANK_WEBHOOK_URL = "https://webhook.example.com/pix"
            client = PixClient()
            return client, mock_httpx_client


class TestPixClientInitialization:
    """Test PixClient initialization."""

    def test_default_environment_is_sandbox(self):
        with patch("app.infrastructure.payments.pix_client.httpx.AsyncClient") as mock_httpx:
            with patch("app.infrastructure.payments.pix_client.settings") as mock_settings:
                mock_settings.STARK_BANK_API_KEY = "key"
                mock_settings.STARK_BANK_ENVIRONMENT = "sandbox"
                mock_settings.STARK_BANK_WEBHOOK_URL = ""
                client = PixClient()
                assert client._environment == "sandbox"
                mock_httpx.assert_called_once()

    def test_invalid_environment_raises_error(self):
        with patch("app.infrastructure.payments.pix_client.settings") as mock_settings:
            mock_settings.STARK_BANK_API_KEY = "key"
            mock_settings.STARK_BANK_ENVIRONMENT = "invalid"
            mock_settings.STARK_BANK_WEBHOOK_URL = ""
            with pytest.raises(PixClientError, match="Invalid environment"):
                PixClient()

    def test_custom_parameters(self):
        with patch("app.infrastructure.payments.pix_client.httpx.AsyncClient") as mock_httpx:
            client = PixClient(
                api_key="custom-key",
                environment="production",
                webhook_url="https://custom.webhook.com",
            )
            assert client._api_key == "custom-key"
            assert client._environment == "production"
            assert client._webhook_url == "https://custom.webhook.com"
            mock_httpx.assert_called_once_with(
                base_url="https://api.starkbank.com/v2",
                headers={
                    "Authorization": "Bearer custom-key",
                    "Content-Type": "application/json",
                    "User-Agent": "AgentPlatform/0.1.0",
                },
                timeout=30.0,
            )


class TestCreateQRCode:
    """Test create_qr_code method."""

    async def test_create_qr_code_success(self, pix_client):
        client, mock_httpx = pix_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "qr-123",
            "brcode": "00020126580014br.gov.bcb.pix0136...",
            "url": "https://starkbank.com/qr/qr-123",
            "status": "created",
            "created": "2026-06-20T22:00:00Z",
        }
        mock_httpx.post.return_value = mock_response

        result = await client.create_qr_code(
            amount=Decimal("10.50"),
            description="Payment for compute",
            payer_name="John Doe",
            payer_document="123.456.789-00",
        )

        assert result["id"] == "qr-123"
        assert result["status"] == "created"
        assert result["amount"] == Decimal("10.50")
        mock_httpx.post.assert_awaited_once_with(
            "/dynamic-brcode",
            json={
                "amount": 1050,
                "description": "Payment for compute",
                "payer_name": "John Doe",
                "expires_in": 3600,
                "payer_document": "123.456.789-00",
                "webhook_url": "https://webhook.example.com/pix",
            },
        )

    async def test_create_qr_code_zero_amount_raises_error(self, pix_client):
        client, _ = pix_client
        with pytest.raises(PixClientError, match="Amount must be greater than zero"):
            await client.create_qr_code(
                amount=Decimal("0"),
                description="test",
                payer_name="Test",
            )

    async def test_create_qr_code_negative_amount_raises_error(self, pix_client):
        client, _ = pix_client
        with pytest.raises(PixClientError, match="Amount must be greater than zero"):
            await client.create_qr_code(
                amount=Decimal("-5"),
                description="test",
                payer_name="Test",
            )

    async def test_create_qr_code_http_error(self, pix_client):
        client, mock_httpx = pix_client
        mock_httpx.post.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=MagicMock(status_code=400, text="Invalid parameters"),
        )

        with pytest.raises(PixClientError, match="Stark Bank API error: 400"):
            await client.create_qr_code(
                amount=Decimal("10"),
                description="test",
                payer_name="Test",
            )

    async def test_create_qr_code_request_error(self, pix_client):
        client, mock_httpx = pix_client
        mock_httpx.post.side_effect = httpx.RequestError("Connection failed")

        with pytest.raises(PixClientError, match="Request failed"):
            await client.create_qr_code(
                amount=Decimal("10"),
                description="test",
                payer_name="Test",
            )

    async def test_create_qr_code_without_webhook(self):
        with patch("app.infrastructure.payments.pix_client.httpx.AsyncClient") as mock_httpx_cls:
            mock_httpx = AsyncMock()
            mock_httpx_cls.return_value = mock_httpx
            with patch("app.infrastructure.payments.pix_client.settings") as mock_settings:
                mock_settings.STARK_BANK_API_KEY = "key"
                mock_settings.STARK_BANK_ENVIRONMENT = "sandbox"
                mock_settings.STARK_BANK_WEBHOOK_URL = ""
                client = PixClient()

            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "qr-123", "brcode": "...", "status": "created"}
            mock_httpx.post.return_value = mock_response

            result = await client.create_qr_code(
                amount=Decimal("25"),
                description="No webhook",
                payer_name="Test",
            )

            assert result["id"] == "qr-123"
            # Verify webhook_url was NOT included in the payload
            call_kwargs = mock_httpx.post.await_args.kwargs
            assert "webhook_url" not in call_kwargs["json"]


class TestCheckPayment:
    """Test check_payment method."""

    async def test_check_payment_paid(self, pix_client):
        client, mock_httpx = pix_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "qr-123",
            "status": "paid",
            "amount": 1050,
            "paid_at": "2026-06-20T22:05:00Z",
            "payer_name": "John Doe",
            "payer_document": "123.456.789-00",
        }
        mock_httpx.get.return_value = mock_response

        result = await client.check_payment("qr-123")

        assert result["id"] == "qr-123"
        assert result["status"] == "paid"
        assert result["amount"] == Decimal("10.50")
        assert result["paid_amount"] == Decimal("10.50")
        assert result["payer"]["name"] == "John Doe"
        mock_httpx.get.assert_awaited_once_with("/dynamic-brcode/qr-123")

    async def test_check_payment_created(self, pix_client):
        client, mock_httpx = pix_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "qr-123",
            "status": "created",
            "amount": 1050,
        }
        mock_httpx.get.return_value = mock_response

        result = await client.check_payment("qr-123")

        assert result["status"] == "created"
        assert "paid_amount" not in result
        assert "payer" not in result

    async def test_check_payment_empty_id_raises_error(self, pix_client):
        client, _ = pix_client
        with pytest.raises(PixClientError, match="qr_code_id is required"):
            await client.check_payment("")

    async def test_check_payment_http_error(self, pix_client):
        client, mock_httpx = pix_client
        mock_httpx.get.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404, text="Not found"),
        )

        with pytest.raises(PixClientError, match="Stark Bank API error: 404"):
            await client.check_payment("invalid-id")

    async def test_check_payment_request_error(self, pix_client):
        client, mock_httpx = pix_client
        mock_httpx.get.side_effect = httpx.RequestError("Timeout")

        with pytest.raises(PixClientError, match="Request failed"):
            await client.check_payment("qr-123")


class TestListTransactions:
    """Test list_transactions method."""

    async def test_list_transactions_success(self, pix_client):
        client, mock_httpx = pix_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "brcodes": [
                {"id": "qr-1", "status": "paid", "amount": 5000, "created": "2026-06-20T20:00:00Z",
                 "paid_at": "2026-06-20T20:05:00Z", "payer_name": "Alice"},
                {"id": "qr-2", "status": "created", "amount": 2500, "created": "2026-06-20T21:00:00Z",
                 "paid_at": None, "payer_name": "Bob"},
            ]
        }
        mock_httpx.get.return_value = mock_response

        result = await client.list_transactions(limit=10)

        assert len(result) == 2
        assert result[0]["id"] == "qr-1"
        assert result[0]["amount"] == Decimal("50.00")
        assert result[1]["id"] == "qr-2"
        assert result[1]["amount"] == Decimal("25.00")
        mock_httpx.get.assert_awaited_once_with("/dynamic-brcode", params={"limit": 10})

    async def test_list_transactions_with_filters(self, pix_client):
        client, mock_httpx = pix_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"brcodes": []}
        mock_httpx.get.return_value = mock_response

        await client.list_transactions(
            limit=5,
            after="2026-06-01T00:00:00Z",
            before="2026-06-30T23:59:59Z",
            status="paid",
        )

        mock_httpx.get.assert_awaited_once_with(
            "/dynamic-brcode",
            params={"limit": 5, "after": "2026-06-01T00:00:00Z",
                    "before": "2026-06-30T23:59:59Z", "status": "paid"},
        )

    async def test_list_transactions_limit_capped_at_100(self, pix_client):
        client, mock_httpx = pix_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"brcodes": []}
        mock_httpx.get.return_value = mock_response

        await client.list_transactions(limit=200)

        mock_httpx.get.assert_awaited_once_with("/dynamic-brcode", params={"limit": 100})

    async def test_list_transactions_http_error(self, pix_client):
        client, mock_httpx = pix_client
        mock_httpx.get.side_effect = httpx.HTTPStatusError(
            "500 Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500, text="Internal error"),
        )

        with pytest.raises(PixClientError, match="Stark Bank API error: 500"):
            await client.list_transactions()


class TestPixClientContextManager:
    """Test async context manager."""

    async def test_async_context_manager(self, mock_httpx_client):
        with patch("app.infrastructure.payments.pix_client.httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("app.infrastructure.payments.pix_client.settings") as mock_settings:
                mock_settings.STARK_BANK_API_KEY = "key"
                mock_settings.STARK_BANK_ENVIRONMENT = "sandbox"
                mock_settings.STARK_BANK_WEBHOOK_URL = ""
                async with PixClient() as client:
                    assert client._client is not None

            mock_httpx_client.aclose.assert_awaited_once()
