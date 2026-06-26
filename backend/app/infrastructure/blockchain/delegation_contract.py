"""EIP-7702 delegation contract interaction.

This module provides the interface to AgentDelegation.sol, which implements
EIP-7702 temporary authority delegation for autonomous agents with budget cap.

Contract ABI aligned with: contracts/src/AgentDelegation.sol
"""
from web3 import Web3
from web3.contract import Contract

from app.core.config import settings
from app.core.exceptions import ContractNotConfiguredError
from app.infrastructure.blockchain.web3_client import Web3Client

# ABI aligned with AgentDelegation.sol (EIP-7702 + Budget Cap)
# Functions: delegate(), delegateBySig(), revoke(), revokeBySig(),
#            isValidDelegation(), getDelegation(), getNonce(),
#            recordSpend(), setSpendRecorder(), getRemainingBudget()
AGENT_DELEGATION_ABI = [
    # delegate(address _delegate, uint256 _expiresAt, uint256 _maxBudget)
    {
        "inputs": [
            {"name": "_delegate", "type": "address"},
            {"name": "_expiresAt", "type": "uint256"},
            {"name": "_maxBudget", "type": "uint256"},
        ],
        "name": "delegate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # delegateBySig(address _agent, address _delegate, uint256 _expiresAt, uint256 _maxBudget, bytes calldata _signature)
    {
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_delegate", "type": "address"},
            {"name": "_expiresAt", "type": "uint256"},
            {"name": "_maxBudget", "type": "uint256"},
            {"name": "_signature", "type": "bytes"},
        ],
        "name": "delegateBySig",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # revoke()
    {
        "inputs": [],
        "name": "revoke",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # revokeBySig(address _agent, bytes calldata _signature)
    {
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_signature", "type": "bytes"},
        ],
        "name": "revokeBySig",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # recordSpend(address _agent, uint256 _amount)
    {
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "recordSpend",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # setSpendRecorder(address _recorder, bool _authorized)
    {
        "inputs": [
            {"name": "_recorder", "type": "address"},
            {"name": "_authorized", "type": "bool"},
        ],
        "name": "setSpendRecorder",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # isValidDelegation(address _agent, address _delegate) view returns (bool)
    {
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_delegate", "type": "address"},
        ],
        "name": "isValidDelegation",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getDelegation(address _agent) view returns (address delegate, uint256 expiresAt, uint256 maxBudget, uint256 spentAmount, bool active)
    {
        "inputs": [{"name": "_agent", "type": "address"}],
        "name": "getDelegation",
        "outputs": [
            {"name": "agent", "type": "address"},
            {"name": "delegate", "type": "address"},
            {"name": "expiresAt", "type": "uint256"},
            {"name": "maxBudget", "type": "uint256"},
            {"name": "spentAmount", "type": "uint256"},
            {"name": "active", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # getNonce(address _agent) view returns (uint256)
    {
        "inputs": [{"name": "_agent", "type": "address"}],
        "name": "getNonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getDelegationHistory(address _agent) view returns (address[])
    {
        "inputs": [{"name": "_agent", "type": "address"}],
        "name": "getDelegationHistory",
        "outputs": [{"name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getRemainingBudget(address _agent) view returns (uint256)
    {
        "inputs": [{"name": "_agent", "type": "address"}],
        "name": "getRemainingBudget",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class DelegationContract:
    """Client for interacting with the EIP-7702 AgentDelegation.sol contract.

    Provides both wallet-based (delegate/revoke) and gasless (delegateBySig/revokeBySig)
    delegation management aligned with the EIP-7702 standard, plus budget cap enforcement
    via recordSpend and getRemainingBudget.
    """

    def __init__(self, web3_client: Web3Client):
        self._client = web3_client
        self._contract: Contract | None = None
        if settings.AGENT_DELEGATION_ADDRESS:
            self._contract = web3_client.w3.eth.contract(
                address=Web3.to_checksum_address(settings.AGENT_DELEGATION_ADDRESS),
                abi=AGENT_DELEGATION_ABI,
            )

    # =========================================================================
    # Wallet-based operations (deployer key required)
    # =========================================================================

    async def delegate(self, delegate_address: str, expires_at: int, max_budget: int) -> str:
        """Set delegation for an agent with a budget cap (requires deployer key).

        Calls delegate(address _delegate, uint256 _expiresAt, uint256 _maxBudget)
        on AgentDelegation.sol.

        Args:
            delegate_address: Address to delegate authority to
            expires_at: Unix timestamp when delegation expires
            max_budget: Maximum spend amount in wei (budget cap)

        Returns:
            Transaction hash hex string
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.delegate(
            Web3.to_checksum_address(delegate_address),
            expires_at,
            max_budget,
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    async def revoke(self) -> str:
        """Revoke current delegation (requires deployer key).

        Calls revoke() on AgentDelegation.sol.

        Returns:
            Transaction hash hex string
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.revoke().build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    async def record_spend(self, agent_address: str, amount: int) -> str:
        """Record a spend against an agent's delegation budget.

        Calls recordSpend(address _agent, uint256 _amount) on AgentDelegation.sol.
        Only callable by authorized spend recorders (e.g., PaymentVerifier).

        Args:
            agent_address: Address of the agent whose budget to deduct from
            amount: Amount spent in wei

        Returns:
            Transaction hash hex string
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.recordSpend(
            Web3.to_checksum_address(agent_address),
            amount,
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    async def set_spend_recorder(self, recorder_address: str, authorized: bool) -> str:
        """Authorize or deauthorize a spend recorder contract.

        Calls setSpendRecorder(address _recorder, bool _authorized) on AgentDelegation.sol.
        Only callable by the contract owner (deployer).

        Args:
            recorder_address: Address of the contract to authorize/deauthorize
            authorized: True to authorize, False to deauthorize

        Returns:
            Transaction hash hex string
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.setSpendRecorder(
            Web3.to_checksum_address(recorder_address),
            authorized,
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    # =========================================================================
    # Gasless operations (EIP-712 signed)
    # =========================================================================

    async def delegate_by_sig(
        self,
        agent_address: str,
        delegate_address: str,
        expires_at: int,
        max_budget: int,
        signature: bytes,
    ) -> str:
        """Gasless delegation via EIP-712 signature with budget cap.

        Calls delegateBySig(address _agent, address _delegate, uint256 _expiresAt,
        uint256 _maxBudget, bytes calldata _signature) on AgentDelegation.sol.
        The agent signs an EIP-712 typed message off-chain, and any account can
        submit the transaction.

        Args:
            agent_address: Address of the agent granting delegation
            delegate_address: Address receiving delegation authority
            expires_at: Unix timestamp when delegation expires
            max_budget: Maximum spend amount in wei (budget cap)
            signature: EIP-712 typed signature bytes (r, s, v packed)

        Returns:
            Transaction hash hex string
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.delegateBySig(
            Web3.to_checksum_address(agent_address),
            Web3.to_checksum_address(delegate_address),
            expires_at,
            max_budget,
            signature,
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 150000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    async def revoke_by_sig(self, agent_address: str, signature: bytes) -> str:
        """Gasless revocation via EIP-712 signature.

        Calls revokeBySig(address _agent, bytes calldata _signature) on AgentDelegation.sol.

        Args:
            agent_address: Address of the agent revoking delegation
            signature: EIP-712 typed signature bytes (r, s, v packed)

        Returns:
            Transaction hash hex string
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")

        account = self._client.w3.eth.account.from_key(settings.CONTRACT_DEPLOYER_KEY)
        tx = self._contract.functions.revokeBySig(
            Web3.to_checksum_address(agent_address),
            signature,
        ).build_transaction({
            "from": account.address,
            "nonce": self._client.w3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": self._client.w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        tx_hash = self._client.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._client.w3.to_hex(tx_hash)

    # =========================================================================
    # Read operations (view functions)
    # =========================================================================

    async def is_valid_delegation(self, agent_address: str, delegate_address: str) -> bool:
        """Check if a delegation is currently valid.

        Calls isValidDelegation(address _agent, address _delegate) view on AgentDelegation.sol.
        Returns True only if delegation exists, is active, and has not expired.
        """
        if not self._contract:
            return False
        return self._contract.functions.isValidDelegation(
            Web3.to_checksum_address(agent_address),
            Web3.to_checksum_address(delegate_address),
        ).call()

    async def get_delegation(self, agent_address: str) -> tuple:
        """Get the current delegation details for an agent.

        Calls getDelegation(address _agent) view on AgentDelegation.sol.

        Returns:
            Tuple of (agent, delegate, expires_at, max_budget, spent_amount, is_active)
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")
        return self._contract.functions.getDelegation(
            Web3.to_checksum_address(agent_address),
        ).call()

    async def get_nonce(self, agent_address: str) -> int:
        """Get the current nonce for an agent (used for EIP-712 replay protection).

        Calls getNonce(address _agent) view on AgentDelegation.sol.
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")
        return self._contract.functions.getNonce(
            Web3.to_checksum_address(agent_address),
        ).call()

    async def get_delegation_history(self, agent_address: str) -> list:
        """Get the delegation history for an agent.

        Calls getDelegationHistory(address _agent) view on AgentDelegation.sol.
        Returns list of addresses that have been delegated to (chronological order).
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")
        return self._contract.functions.getDelegationHistory(
            Web3.to_checksum_address(agent_address),
        ).call()

    async def get_remaining_budget(self, agent_address: str) -> int:
        """Get the remaining budget for an agent's delegation.

        Calls getRemainingBudget(address _agent) view on AgentDelegation.sol.
        Returns the remaining budget in wei (maxBudget - spentAmount), or 0 if
        no active delegation or budget exhausted.
        """
        if not self._contract:
            raise ContractNotConfiguredError(contract_name="AgentDelegation")
        return self._contract.functions.getRemainingBudget(
            Web3.to_checksum_address(agent_address),
        ).call()
