"""x402 payment verification service."""
from web3 import Web3
from app.core.config import settings
from app.infrastructure.blockchain.web3_client import Web3Client
from app.core.exceptions import (
    PaymentVerificationError,
    TransactionNotFoundError,
    TransactionFailedError,
    SenderMismatchError,
    RecipientMismatchError,
    AmountMismatchError,
)


class PaymentVerifier:
    """Verifies x402 micropayments on-chain."""

    def __init__(self, web3_client: Web3Client):
        self._client = web3_client
        self._verifier_address = Web3.to_checksum_address(settings.PAYMENT_VERIFIER_ADDRESS) if settings.PAYMENT_VERIFIER_ADDRESS else None

    async def verify_payment(self, payment_proof: dict) -> dict:
        """
        Verify an x402 payment receipt.

        Expected payment_proof format:
        {
            "tx_hash": "0x...",
            "sender": "0x...",
            "recipient": "0x...",
            "amount": 100000,
            "block_number": 123456,
            "signature": "0x..."
        }
        """
        tx_hash = payment_proof.get("tx_hash")
        if not tx_hash:
            raise PaymentVerificationError(reason="Missing tx_hash in payment proof")

        # Get transaction receipt
        receipt = self._client.w3.eth.get_transaction_receipt(tx_hash)
        if receipt is None:
            raise TransactionNotFoundError(tx_hash=tx_hash)

        # Verify transaction was successful
        if receipt["status"] != 1:
            raise TransactionFailedError(tx_hash=tx_hash, status=receipt["status"])

        # Get transaction details
        tx = self._client.w3.eth.get_transaction(tx_hash)
        sender = payment_proof.get("sender", "").lower()
        recipient = payment_proof.get("recipient", "").lower()

        if tx["from"].lower() != sender:
            raise SenderMismatchError(expected=sender, actual=tx["from"].lower())
        if tx["to"] and tx["to"].lower() != recipient:
            raise RecipientMismatchError(expected=recipient, actual=tx["to"].lower())
        if tx["value"] < payment_proof.get("amount", 0):
            raise AmountMismatchError(
                expected=payment_proof.get("amount", 0),
                actual=tx["value"],
            )

        return {
            "verified": True,
            "tx_hash": tx_hash,
            "block_number": receipt["blockNumber"],
            "amount": tx["value"],
            "sender": sender,
            "recipient": recipient,
        }

    async def verify_payment_receipt(self, receipt_data: dict) -> bool:
        """Verify a signed payment receipt off-chain."""
        message = Web3.solidity_keccak(
            ["address", "address", "uint256", "uint256"],
            [
                receipt_data.get("sender", ""),
                receipt_data.get("recipient", ""),
                receipt_data.get("amount", 0),
                receipt_data.get("nonce", 0),
            ],
        )
        signature = bytes.fromhex(receipt_data.get("signature", "").replace("0x", ""))
        return await self._client.verify_signature(message, signature, receipt_data.get("sender", ""))
