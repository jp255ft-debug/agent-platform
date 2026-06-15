"""Integration tests for PixClient (Stark Bank).

Tests follow the BUILD_GUIDE.md §16 patterns and use pytest-asyncio.

Prerequisites:
    - STARK_BANK_API_KEY environment variable set (sandbox key)
    - STARK_BANK_ENVIRONMENT set to "sandbox"

Run with:
    pytest tests/integration/test_pix_client.py -v --asyncio-mode=auto
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.payments.pix_client import PixClient, PixClientError


@pytest.fixture
def pix_client():
    """Create a PixClient instance with a mock API key for testing."""
    client = PixClient(
        api_key="test-api-key",
        environment="sandbox",
    )
    yield client


class TestPixClientInitialization:
    """Test PixClient initialization and configuration."""

    def test_init_with_defaults(self):
        """Should initialize with default sandbox environment."""
        client = PixClient(api_key="test-key")
        assert client._environment == "sandbox"
        assert client._api_key == "test-key"

    def test_init_with_production(self):
        """Should use production URL when specified."""
        client = PixClient(api_key="test-key", environment="production")
        assert client._environment == "production"
        assert "api.starkbank.com/v2" in str(client._client.base_url)

    def test_init_invalid_environment(self):
        """Should raise error for invalid environment."""
        with pytest.raises(PixClientError, match="Invalid environment"):
            PixClient(api_key="test-key", environment="invalid")


class TestPixClientCreateQRCode:
    """Test QR Code generation."""

    @pytest.mark.asyncio
    async def test_create_qr_code_success(self, pix_client):
        """Should successfully create a dynamic QR Code."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789",
            "brcode": "00020126580014br.gov.bcb.pix0136test@starkbank.com520400005303986540510.005802BR5913Test Payer6009Sao Paulo62070503***63041234",
            "url": "https://starkbank.com/pix/123456789",
            "status": "created",
            "created": "2026-06-13T10:00:00.000Z",
            "amount": 1050,
        }

        with patch.object(pix_client._client, "post", return_value=mock_response):
            result = await pix_client.create_qr_code(
                amount=Decimal("10.50"),
                description="Test payment",
                payer_name="Test Payer",
            )

        assert result["id"] == "123456789"
        assert result["status"] == "created"
        assert result["amount"] == Decimal("10.50")
        assert "br.gov.bcb.pix" in result["qr_code"]

    @pytest.mark.asyncio
    async def test_create_qr_code_with_document(self, pix_client):
        """Should include payer document when provided."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "987654321",
            "brcode": "00020126580014br.gov.bcb.pix...",
            "status": "created",
            "created": "2026-06-13T10:00:00.000Z",
            "amount": 5000,
        }

        with patch.object(pix_client._client, "post", return_value=mock_response):
            result = await pix_client.create_qr_code(
                amount=Decimal("50.00"),
                description="Payment with document",
                payer_name="Company XYZ",
                payer_document="12.345.678/0001-90",
            )

        assert result["status"] == "created"
        assert result["amount"] == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_create_qr_code_zero_amount(self, pix_client):
        """Should reject zero or negative amounts."""
        with pytest.raises(PixClientError, match="Amount must be greater than zero"):
            await pix_client.create_qr_code(
                amount=Decimal("0"),
                description="Zero amount",
                payer_name="Test",
            )

    @pytest.mark.asyncio
    async def test_create_qr_code_api_error(self, pix_client):
        """Should handle Stark Bank API errors gracefully."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 400
        mock_response.text = '{"message": "Invalid amount"}'
        mock_response.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        with patch.object(pix_client._client, "post", return_value=mock_response):
            with pytest.raises(PixClientError, match="Stark Bank API error"):
                await pix_client.create_qr_code(
                    amount=Decimal("999999.99"),
                    description="Too large",
                    payer_name="Test",
                )


class TestPixClientCheckPayment:
    """Test payment status checking."""

    @pytest.mark.asyncio
    async def test_check_payment_paid(self, pix_client):
        """Should return payment details when paid."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789",
            "status": "paid",
            "amount": 1050,
            "paid_at": "2026-06-13T10:05:00.000Z",
            "payer_name": "Test Payer",
            "payer_document": "123.456.789-00",
        }

        with patch.object(pix_client._client, "get", return_value=mock_response):
            result = await pix_client.check_payment("123456789")

        assert result["status"] == "paid"
        assert result["paid_amount"] == Decimal("10.50")
        assert result["payer"]["name"] == "Test Payer"

    @pytest.mark.asyncio
    async def test_check_payment_pending(self, pix_client):
        """Should return pending status when not yet paid."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789",
            "status": "created",
            "amount": 1050,
        }

        with patch.object(pix_client._client, "get", return_value=mock_response):
            result = await pix_client.check_payment("123456789")

        assert result["status"] == "created"
        assert "paid_amount" not in result

    @pytest.mark.asyncio
    async def test_check_payment_empty_id(self, pix_client):
        """Should reject empty QR Code ID."""
        with pytest.raises(PixClientError, match="qr_code_id is required"):
            await pix_client.check_payment("")


class TestPixClientListTransactions:
    """Test transaction listing."""

    @pytest.mark.asyncio
    async def test_list_transactions_default(self, pix_client):
        """Should list recent transactions."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "brcodes": [
                {
                    "id": "1",
                    "status": "paid",
                    "amount": 1000,
                    "created": "2026-06-13T10:00:00.000Z",
                    "paid_at": "2026-06-13T10:05:00.000Z",
                    "payer_name": "Alice",
                },
                {
                    "id": "2",
                    "status": "created",
                    "amount": 2000,
                    "created": "2026-06-13T10:10:00.000Z",
                    "payer_name": "Bob",
                },
            ]
        }

        with patch.object(pix_client._client, "get", return_value=mock_response):
            transactions = await pix_client.list_transactions(limit=10)

        assert len(transactions) == 2
        assert transactions[0]["status"] == "paid"
        assert transactions[0]["amount"] == Decimal("10.00")
        assert transactions[1]["status"] == "created"
        assert transactions[1]["amount"] == Decimal("20.00")

    @pytest.mark.asyncio
    async def test_list_transactions_empty(self, pix_client):
        """Should return empty list when no transactions."""
        mock_response = MagicMock(spec=__import__("httpx").Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"brcodes": []}

        with patch.object(pix_client._client, "get", return_value=mock_response):
            transactions = await pix_client.list_transactions()

        assert transactions == []


class TestPixClientContextManager:
    """Test async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Should work as async context manager."""
        async with PixClient(api_key="test-key") as client:
            assert client._api_key == "test-key"
            assert client._environment == "sandbox"
