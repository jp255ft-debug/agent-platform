"""Web3 client for blockchain interactions."""
from web3 import Web3

from app.core.config import settings


class Web3Client:
    """Client for interacting with Ethereum-compatible blockchains."""

    def __init__(self):
        self._w3 = Web3(Web3.HTTPProvider(settings.RPC_URL_BASE))
        # geth_poa_middleware is injected conditionally for PoA chains
        try:
            from web3.middleware import geth_poa_middleware  # type: ignore[attr-defined]
            self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except ImportError:
            pass

    @property
    def w3(self) -> Web3:
        return self._w3

    async def is_connected(self) -> bool:
        return self._w3.is_connected()

    async def get_block_number(self) -> int:
        return self._w3.eth.block_number

    async def get_balance(self, address: str) -> int:
        return self._w3.eth.get_balance(Web3.to_checksum_address(address))

    async def verify_signature(self, message: bytes, signature: bytes, signer: str) -> bool:
        """Verify an Ethereum signed message."""
        recovered = self._w3.eth.account.recover_message(message, signature=signature)
        return recovered.lower() == signer.lower()
