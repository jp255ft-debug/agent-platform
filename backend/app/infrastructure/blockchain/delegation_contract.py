"""EIP-7702 delegation contract interaction."""
from web3 import Web3
from web3.contract import Contract
from app.core.config import settings
from app.infrastructure.blockchain.web3_client import Web3Client
from app.core.exceptions import ContractNotConfiguredError


# Minimal ABI for delegation contract
DELEGATION_CONTRACT_ABI = [
    {
        "inputs": [{"name": "agent", "type": "address"}, {"name": "delegate", "type": "address"}],
        "name": "setDelegation",
        "type": "function",
        "stateMutability": "nonpayable",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "getDelegation",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
        "stateMutability": "view",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "revokeDelegation",
        "type": "function",
        "stateMutability": "nonpayable",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "isDelegationActive",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
        "stateMutability": "view",
    },
]


class DelegationContract:
    """Client for interacting with the EIP-7702 delegation contract."""

    def __init__(self, web3_client: Web3Client):
        self._client = web3_client
        self._contract: Contract | None = None
        if settings.AGENT_DELEGATION_ADDRESS:
            self._contract = web3_client.w3.eth.contract(
                address=Web3.to_checksum_address(settings.AGENT_DELEGATION_ADDRESS),
                abi=DELEGATION_CONTRACT_ABI,
            )

    async def set_delegation(self, agent_address: str, delegate_address: str) -> str:
        """Set delegation for an agent (requires deployer key)."""
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.setDelegation(
            Web3.to_checksum_address(agent_address),
            Web3.to_checksum_address(delegate_address),
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    async def get_delegation(self, agent_address: str) -> str:
        """Get the delegated address for an agent."""
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")
        return await self._contract.functions.getDelegation(
            Web3.to_checksum_address(agent_address),
        ).call()

    async def revoke_delegation(self, agent_address: str) -> str:
        """Revoke delegation for an agent."""
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.revokeDelegation(
            Web3.to_checksum_address(agent_address),
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    async def is_delegation_active(self, agent_address: str) -> bool:
        """Check if delegation is active for an agent."""
        if not self._contract:
            return False
        return await self._contract.functions.isDelegationActive(
            Web3.to_checksum_address(agent_address),
        ).call()
