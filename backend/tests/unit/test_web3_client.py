"""Unit tests for Web3Client."""
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.blockchain.web3_client import Web3Client


@pytest.fixture
def mock_w3():
    """Create a mock Web3 instance."""
    w3 = MagicMock()
    w3.is_connected = MagicMock(return_value=True)
    w3.eth = MagicMock()
    w3.eth.block_number = 123456
    w3.eth.get_balance = MagicMock(return_value=1000000000000000000)
    w3.eth.account = MagicMock()
    w3.eth.account.recover_message = MagicMock(return_value="0x1234567890abcdef1234567890abcdef12345678")
    w3.middleware_onion = MagicMock()
    w3.middleware_onion.inject = MagicMock()
    return w3


@pytest.fixture
def web3_client(mock_w3):
    """Create a Web3Client with mocked Web3."""
    with patch("app.infrastructure.blockchain.web3_client.Web3") as mock_web3_cls:
        mock_web3_cls.HTTPProvider = MagicMock()
        mock_web3_cls.to_checksum_address = MagicMock(side_effect=lambda x: x)
        mock_web3_cls.return_value = mock_w3
        with patch("app.infrastructure.blockchain.web3_client.settings") as mock_settings:
            mock_settings.RPC_URL_BASE = "https://sepolia.base.org"
            client = Web3Client()
            return client, mock_w3


class TestWeb3ClientInitialization:
    """Test Web3Client initialization."""

    def test_initializes_web3_with_rpc_url(self, mock_w3):
        with patch("app.infrastructure.blockchain.web3_client.Web3") as mock_web3_cls:
            mock_web3_cls.HTTPProvider = MagicMock()
            mock_web3_cls.return_value = mock_w3
            with patch("app.infrastructure.blockchain.web3_client.settings") as mock_settings:
                mock_settings.RPC_URL_BASE = "https://mainnet.base.org"
                client = Web3Client()

                mock_web3_cls.HTTPProvider.assert_called_once_with("https://mainnet.base.org")
                mock_web3_cls.assert_called_once()

    def test_injects_poa_middleware(self, mock_w3):
        with patch("app.infrastructure.blockchain.web3_client.Web3") as mock_web3_cls:
            mock_web3_cls.HTTPProvider = MagicMock()
            mock_web3_cls.return_value = mock_w3
            with patch("app.infrastructure.blockchain.web3_client.settings") as mock_settings:
                mock_settings.RPC_URL_BASE = "https://sepolia.base.org"
                client = Web3Client()

                mock_w3.middleware_onion.inject.assert_called_once()

    def test_w3_property(self, web3_client):
        client, mock_w3 = web3_client
        assert client.w3 == mock_w3


class TestIsConnected:
    """Test is_connected method."""

    async def test_is_connected_true(self, web3_client):
        client, mock_w3 = web3_client
        mock_w3.is_connected.return_value = True

        result = await client.is_connected()
        assert result is True

    async def test_is_connected_false(self, web3_client):
        client, mock_w3 = web3_client
        mock_w3.is_connected.return_value = False

        result = await client.is_connected()
        assert result is False


class TestGetBlockNumber:
    """Test get_block_number method."""

    async def test_get_block_number(self, web3_client):
        client, mock_w3 = web3_client
        mock_w3.eth.block_number = 999999

        result = await client.get_block_number()
        assert result == 999999


class TestGetBalance:
    """Test get_balance method."""

    async def test_get_balance(self, web3_client):
        client, mock_w3 = web3_client
        address = "0x1234567890abcdef1234567890abcdef12345678"
        mock_w3.eth.get_balance.return_value = 5000000000000000000

        result = await client.get_balance(address)
        assert result == 5000000000000000000
        mock_w3.eth.get_balance.assert_called_once_with(address)


class TestVerifySignature:
    """Test verify_signature method."""

    async def test_verify_signature_valid(self, web3_client):
        client, mock_w3 = web3_client
        message = b"hello world"
        signature = b"\x01\x02\x03\x04"
        signer = "0x1234567890abcdef1234567890abcdef12345678"

        mock_w3.eth.account.recover_message.return_value = signer

        result = await client.verify_signature(message, signature, signer)
        assert result is True
        mock_w3.eth.account.recover_message.assert_called_once_with(message, signature=signature)

    async def test_verify_signature_invalid(self, web3_client):
        client, mock_w3 = web3_client
        message = b"hello world"
        signature = b"\x05\x06\x07\x08"
        signer = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        mock_w3.eth.account.recover_message.return_value = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

        result = await client.verify_signature(message, signature, signer)
        assert result is False

    async def test_verify_signature_case_insensitive(self, web3_client):
        """Should handle mixed-case addresses."""
        client, mock_w3 = web3_client
        message = b"test"
        signature = b"\x00\x01\x02\x03"
        signer = "0x1234567890ABCDEF1234567890ABCDEF12345678"

        mock_w3.eth.account.recover_message.return_value = "0x1234567890abcdef1234567890abcdef12345678"

        result = await client.verify_signature(message, signature, signer)
        assert result is True
