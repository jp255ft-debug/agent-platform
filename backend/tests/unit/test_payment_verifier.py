"""Unit tests for PaymentVerifier."""
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.blockchain.payment_verifier import PaymentVerifier
from app.core.exceptions import (
    PaymentVerificationError,
    TransactionNotFoundError,
    TransactionFailedError,
    SenderMismatchError,
    RecipientMismatchError,
    AmountMismatchError,
)


@pytest.fixture
def mock_web3_client():
    """Create a mock Web3Client."""
    client = MagicMock()
    client.w3 = MagicMock()
    client.w3.eth = MagicMock()
    client.w3.to_checksum_address = MagicMock(side_effect=lambda x: x)
    client.verify_signature = MagicMock()
    return client


@pytest.fixture
def verifier(mock_web3_client):
    """Create a PaymentVerifier with mocked Web3Client."""
    with patch("app.infrastructure.blockchain.payment_verifier.settings") as mock_settings:
        mock_settings.PAYMENT_VERIFIER_ADDRESS = "0x1234567890123456789012345678901234567890"
        return PaymentVerifier(mock_web3_client)


@pytest.fixture
def verifier_no_address(mock_web3_client):
    """Create a PaymentVerifier without a verifier address configured."""
    with patch("app.infrastructure.blockchain.payment_verifier.settings") as mock_settings:
        mock_settings.PAYMENT_VERIFIER_ADDRESS = None
        return PaymentVerifier(mock_web3_client)


def make_valid_proof(**overrides):
    """Create a valid payment proof dict with sensible defaults."""
    proof = {
        "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "sender": "0x1234567890abcdef1234567890abcdef12345678",
        "recipient": "0xabcdef1234567890abcdef1234567890abcdef12",
        "amount": 100000,
        "block_number": 123456,
        "signature": "0x" + "ab" * 65,
    }
    proof.update(overrides)
    return proof


def make_receipt(**overrides):
    """Create a mock transaction receipt."""
    receipt = {
        "status": 1,
        "blockNumber": 123456,
        "transactionHash": "0xabc",
        "blockHash": "0xdef",
        "from": "0x1234567890abcdef1234567890abcdef12345678",
        "to": "0xabcdef1234567890abcdef1234567890abcdef12",
        "cumulativeGasUsed": 21000,
        "gasUsed": 21000,
        "logs": [],
    }
    receipt.update(overrides)
    return receipt


def make_tx(**overrides):
    """Create a mock transaction dict."""
    tx = {
        "from": "0x1234567890abcdef1234567890abcdef12345678",
        "to": "0xabcdef1234567890abcdef1234567890abcdef12",
        "value": 100000,
        "gas": 21000,
        "gasPrice": 20000000000,
        "nonce": 1,
        "input": "0x",
        "blockNumber": 123456,
        "blockHash": "0xdef",
        "transactionIndex": 0,
    }
    tx.update(overrides)
    return tx


class TestPaymentVerifierInitialization:
    """Test PaymentVerifier initialization."""

    def test_verifier_address_set(self, mock_web3_client):
        with patch("app.infrastructure.blockchain.payment_verifier.settings") as mock_settings:
            mock_settings.PAYMENT_VERIFIER_ADDRESS = "0x1234567890123456789012345678901234567890"
            verifier = PaymentVerifier(mock_web3_client)
            assert verifier._verifier_address == "0x1234567890123456789012345678901234567890"

    def test_verifier_address_none(self, mock_web3_client):
        with patch("app.infrastructure.blockchain.payment_verifier.settings") as mock_settings:
            mock_settings.PAYMENT_VERIFIER_ADDRESS = None
            verifier = PaymentVerifier(mock_web3_client)
            assert verifier._verifier_address is None


class TestVerifyPayment:
    """Test verify_payment method."""

    async def test_verify_payment_success(self, verifier, mock_web3_client):
        """Should return verified result when all checks pass."""
        proof = make_valid_proof()
        receipt = make_receipt()
        tx = make_tx()

        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        result = await verifier.verify_payment(proof)

        assert result["verified"] is True
        assert result["tx_hash"] == proof["tx_hash"]
        assert result["block_number"] == 123456
        assert result["amount"] == 100000
        assert result["sender"] == proof["sender"].lower()
        assert result["recipient"] == proof["recipient"].lower()

    async def test_verify_payment_missing_tx_hash(self, verifier):
        """Should raise PaymentVerificationError when tx_hash is missing."""
        proof = make_valid_proof(tx_hash=None)

        with pytest.raises(PaymentVerificationError, match="Missing tx_hash"):
            await verifier.verify_payment(proof)

    async def test_verify_payment_empty_tx_hash(self, verifier):
        """Should raise PaymentVerificationError when tx_hash is empty."""
        proof = make_valid_proof(tx_hash="")

        with pytest.raises(PaymentVerificationError, match="Missing tx_hash"):
            await verifier.verify_payment(proof)

    async def test_verify_payment_transaction_not_found(self, verifier, mock_web3_client):
        """Should raise TransactionNotFoundError when receipt is None."""
        proof = make_valid_proof()
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = None

        with pytest.raises(TransactionNotFoundError, match=proof["tx_hash"]):
            await verifier.verify_payment(proof)

    async def test_verify_payment_transaction_failed(self, verifier, mock_web3_client):
        """Should raise TransactionFailedError when status is not 1."""
        proof = make_valid_proof()
        receipt = make_receipt(status=0)
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt

        with pytest.raises(TransactionFailedError, match=proof["tx_hash"]):
            await verifier.verify_payment(proof)

    async def test_verify_payment_sender_mismatch(self, verifier, mock_web3_client):
        """Should raise SenderMismatchError when sender doesn't match."""
        proof = make_valid_proof(sender="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        receipt = make_receipt()
        tx = make_tx(from_="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        with pytest.raises(SenderMismatchError):
            await verifier.verify_payment(proof)

    async def test_verify_payment_recipient_mismatch(self, verifier, mock_web3_client):
        """Should raise RecipientMismatchError when recipient doesn't match."""
        proof = make_valid_proof(recipient="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        receipt = make_receipt()
        tx = make_tx(to_="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        with pytest.raises(RecipientMismatchError):
            await verifier.verify_payment(proof)

    async def test_verify_payment_recipient_none(self, verifier, mock_web3_client):
        """Should not raise when tx.to is None (contract creation)."""
        proof = make_valid_proof(recipient="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        receipt = make_receipt()
        tx = make_tx(to_=None)
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        # Should not raise RecipientMismatchError because tx.to is None
        result = await verifier.verify_payment(proof)
        assert result["verified"] is True

    async def test_verify_payment_amount_mismatch(self, verifier, mock_web3_client):
        """Should raise AmountMismatchError when amount is less than expected."""
        proof = make_valid_proof(amount=200000)  # expects 200000
        receipt = make_receipt()
        tx = make_tx(value=100000)  # actual is 100000
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        with pytest.raises(AmountMismatchError):
            await verifier.verify_payment(proof)

    async def test_verify_payment_amount_equal(self, verifier, mock_web3_client):
        """Should succeed when amount matches exactly."""
        proof = make_valid_proof(amount=100000)
        receipt = make_receipt()
        tx = make_tx(value=100000)
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        result = await verifier.verify_payment(proof)
        assert result["verified"] is True

    async def test_verify_payment_amount_greater_than_expected(self, verifier, mock_web3_client):
        """Should succeed when actual amount is greater than expected."""
        proof = make_valid_proof(amount=50000)  # expects 50000
        receipt = make_receipt()
        tx = make_tx(value=100000)  # actual is 100000 (more than expected)
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        result = await verifier.verify_payment(proof)
        assert result["verified"] is True

    async def test_verify_payment_case_insensitive_addresses(self, verifier, mock_web3_client):
        """Should handle mixed-case addresses correctly."""
        proof = make_valid_proof(
            sender="0x1234567890ABCDEF1234567890ABCDEF12345678",
            recipient="0xABCDEF1234567890ABCDEF1234567890ABCDEF12",
        )
        receipt = make_receipt()
        tx = make_tx()
        mock_web3_client.w3.eth.get_transaction_receipt.return_value = receipt
        mock_web3_client.w3.eth.get_transaction.return_value = tx

        result = await verifier.verify_payment(proof)
        assert result["verified"] is True
        assert result["sender"] == "0x1234567890abcdef1234567890abcdef12345678"
        assert result["recipient"] == "0xabcdef1234567890abcdef1234567890abcdef12"


class TestVerifyPaymentReceipt:
    """Test verify_payment_receipt method."""

    async def test_verify_payment_receipt_valid(self, verifier, mock_web3_client):
        """Should return True when signature is valid."""
        mock_web3_client.verify_signature.return_value = True

        receipt_data = {
            "sender": "0x1234567890abcdef1234567890abcdef12345678",
            "recipient": "0xabcdef1234567890abcdef1234567890abcdef12",
            "amount": 100000,
            "nonce": 1,
            "signature": "0x" + "ab" * 65,
        }

        result = await verifier.verify_payment_receipt(receipt_data)
        assert result is True
        mock_web3_client.verify_signature.assert_called_once()

    async def test_verify_payment_receipt_invalid(self, verifier, mock_web3_client):
        """Should return False when signature is invalid."""
        mock_web3_client.verify_signature.return_value = False

        receipt_data = {
            "sender": "0x1234567890abcdef1234567890abcdef12345678",
            "recipient": "0xabcdef1234567890abcdef1234567890abcdef12",
            "amount": 100000,
            "nonce": 1,
            "signature": "0x" + "cd" * 65,
        }

        result = await verifier.verify_payment_receipt(receipt_data)
        assert result is False

    async def test_verify_payment_receipt_missing_fields(self, verifier, mock_web3_client):
        """Should handle gracefully when fields are missing."""
        receipt_data = {
            "sender": "",
            "recipient": "",
            "amount": 0,
            "nonce": 0,
            "signature": "0x",
        }

        # Should not raise, just return False since signature is empty
        result = await verifier.verify_payment_receipt(receipt_data)
        assert result is False
