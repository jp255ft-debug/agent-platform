"""Unit tests for DelegationContract."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.blockchain.delegation_contract import DelegationContract
from app.core.exceptions import ContractNotConfiguredError


@pytest.fixture
def mock_web3_client():
    """Create a mock Web3Client with all necessary mocks."""
    client = MagicMock()
    client.w3 = MagicMock()
    client.w3.to_hex = MagicMock(side_effect=lambda x: f"0x{x.hex()}" if hasattr(x, 'hex') else f"0x{x}")
    client.w3.eth = MagicMock()
    client.w3.eth.account = MagicMock()
    client.w3.eth.contract = MagicMock()
    return client


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.address = "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18"
    return account


@pytest.fixture
def mock_contract():
    contract = MagicMock()
    contract.functions = MagicMock()
    return contract


@pytest.fixture
def settings_no_address():
    """Patch settings to have no AGENT_DELEGATION_ADDRESS."""
    with patch("app.infrastructure.blockchain.delegation_contract.settings") as mock_settings:
        mock_settings.AGENT_DELEGATION_ADDRESS = None
        mock_settings.CONTRACT_DEPLOYER_KEY = "0xkey"
        yield mock_settings


@pytest.fixture
def settings_with_address():
    """Patch settings to have a valid AGENT_DELEGATION_ADDRESS."""
    with patch("app.infrastructure.blockchain.delegation_contract.settings") as mock_settings:
        mock_settings.AGENT_DELEGATION_ADDRESS = "0x1234567890123456789012345678901234567890"
        mock_settings.CONTRACT_DEPLOYER_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        yield mock_settings


class TestDelegationContractInitialization:
    """Test contract initialization behavior."""

    def test_contract_not_initialized_without_address(self, mock_web3_client, settings_no_address):
        """When AGENT_DELEGATION_ADDRESS is not set, contract should be None."""
        contract = DelegationContract(mock_web3_client)
        assert contract._contract is None
        mock_web3_client.w3.eth.contract.assert_not_called()

    def test_contract_initialized_with_address(self, mock_web3_client, settings_with_address):
        """When AGENT_DELEGATION_ADDRESS is set, contract should be created."""
        mock_web3_client.w3.eth.contract.return_value = MagicMock()
        contract = DelegationContract(mock_web3_client)
        assert contract._contract is not None
        mock_web3_client.w3.eth.contract.assert_called_once()


class TestDelegationContractWriteOperations:
    """Test write operations (delegate, revoke, record_spend, set_spend_recorder)."""

    @pytest.fixture
    def contract(self, mock_web3_client, settings_with_address, mock_contract):
        mock_web3_client.w3.eth.contract.return_value = mock_contract
        mock_web3_client.w3.eth.account.from_key.return_value = MagicMock(address="0xaddr")
        mock_web3_client.w3.eth.get_transaction_count.return_value = 1
        mock_web3_client.w3.eth.gas_price = 20000000000
        mock_web3_client.w3.eth.send_raw_transaction.return_value = b'\x01\x02\x03'
        mock_web3_client.w3.to_hex.return_value = "0x010203"
        return DelegationContract(mock_web3_client)

    async def test_delegate_success(self, contract, mock_contract):
        func_mock = MagicMock()
        mock_contract.functions.delegate.return_value = func_mock
        func_mock.build_transaction.return_value = {"from": "0xaddr", "nonce": 1, "gas": 100000, "gasPrice": 20000000000}

        tx_hash = await contract.delegate(
            delegate_address="0xabcdef1234567890abcdef1234567890abcdef12",
            expires_at=9999999999,
            max_budget=1000000,
        )

        assert tx_hash == "0x010203"
        mock_contract.functions.delegate.assert_called_once()
        func_mock.build_transaction.assert_called_once()

    async def test_revoke_success(self, contract, mock_contract):
        func_mock = MagicMock()
        mock_contract.functions.revoke.return_value = func_mock
        func_mock.build_transaction.return_value = {"from": "0xaddr", "nonce": 1, "gas": 100000, "gasPrice": 20000000000}

        tx_hash = await contract.revoke()
        assert tx_hash == "0x010203"
        mock_contract.functions.revoke.assert_called_once()

    async def test_record_spend_success(self, contract, mock_contract):
        func_mock = MagicMock()
        mock_contract.functions.recordSpend.return_value = func_mock
        func_mock.build_transaction.return_value = {"from": "0xaddr", "nonce": 1, "gas": 100000, "gasPrice": 20000000000}

        tx_hash = await contract.record_spend(
            agent_address="0xabcdef1234567890abcdef1234567890abcdef12",
            amount=50000,
        )
        assert tx_hash == "0x010203"
        mock_contract.functions.recordSpend.assert_called_once()

    async def test_set_spend_recorder_success(self, contract, mock_contract):
        func_mock = MagicMock()
        mock_contract.functions.setSpendRecorder.return_value = func_mock
        func_mock.build_transaction.return_value = {"from": "0xaddr", "nonce": 1, "gas": 100000, "gasPrice": 20000000000}

        tx_hash = await contract.set_spend_recorder(
            recorder_address="0xabcdef1234567890abcdef1234567890abcdef12",
            authorized=True,
        )
        assert tx_hash == "0x010203"
        mock_contract.functions.setSpendRecorder.assert_called_once()

    async def test_delegate_by_sig_success(self, contract, mock_contract):
        func_mock = MagicMock()
        mock_contract.functions.delegateBySig.return_value = func_mock
        func_mock.build_transaction.return_value = {"from": "0xaddr", "nonce": 1, "gas": 150000, "gasPrice": 20000000000}

        tx_hash = await contract.delegate_by_sig(
            agent_address="0xagent",
            delegate_address="0xdelegate",
            expires_at=9999999999,
            max_budget=1000000,
            signature=b'\x01\x02\x03\x04',
        )
        assert tx_hash == "0x010203"
        mock_contract.functions.delegateBySig.assert_called_once()

    async def test_revoke_by_sig_success(self, contract, mock_contract):
        func_mock = MagicMock()
        mock_contract.functions.revokeBySig.return_value = func_mock
        func_mock.build_transaction.return_value = {"from": "0xaddr", "nonce": 1, "gas": 100000, "gasPrice": 20000000000}

        tx_hash = await contract.revoke_by_sig(
            agent_address="0xagent",
            signature=b'\x01\x02\x03\x04',
        )
        assert tx_hash == "0x010203"
        mock_contract.functions.revokeBySig.assert_called_once()


class TestDelegationContractReadOperations:
    """Test read operations (is_valid_delegation, get_delegation, etc.)."""

    @pytest.fixture
    def contract(self, mock_web3_client, settings_with_address, mock_contract):
        mock_web3_client.w3.eth.contract.return_value = mock_contract
        return DelegationContract(mock_web3_client)

    async def test_is_valid_delegation_true(self, contract, mock_contract):
        func_mock = MagicMock()
        func_mock.call.return_value = True
        mock_contract.functions.isValidDelegation.return_value = func_mock

        result = await contract.is_valid_delegation(
            agent_address="0xagent",
            delegate_address="0xdelegate",
        )
        assert result is True

    async def test_is_valid_delegation_false(self, contract, mock_contract):
        func_mock = MagicMock()
        func_mock.call.return_value = False
        mock_contract.functions.isValidDelegation.return_value = func_mock

        result = await contract.is_valid_delegation(
            agent_address="0xagent",
            delegate_address="0xdelegate",
        )
        assert result is False

    async def test_get_delegation(self, contract, mock_contract):
        expected = ("0xagent", "0xdelegate", 9999999999, 1000000, 50000, True)
        func_mock = MagicMock()
        func_mock.call.return_value = expected
        mock_contract.functions.getDelegation.return_value = func_mock

        result = await contract.get_delegation(agent_address="0xagent")
        assert result == expected

    async def test_get_nonce(self, contract, mock_contract):
        func_mock = MagicMock()
        func_mock.call.return_value = 5
        mock_contract.functions.getNonce.return_value = func_mock

        result = await contract.get_nonce(agent_address="0xagent")
        assert result == 5

    async def test_get_delegation_history(self, contract, mock_contract):
        expected = ["0xdelegate1", "0xdelegate2"]
        func_mock = MagicMock()
        func_mock.call.return_value = expected
        mock_contract.functions.getDelegationHistory.return_value = func_mock

        result = await contract.get_delegation_history(agent_address="0xagent")
        assert result == expected

    async def test_get_remaining_budget(self, contract, mock_contract):
        func_mock = MagicMock()
        func_mock.call.return_value = 950000
        mock_contract.functions.getRemainingBudget.return_value = func_mock

        result = await contract.get_remaining_budget(agent_address="0xagent")
        assert result == 950000


class TestDelegationContractWithoutContract:
    """Test behavior when contract is not configured."""

    @pytest.fixture
    def contract(self, mock_web3_client, settings_no_address):
        return DelegationContract(mock_web3_client)

    async def test_delegate_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.delegate("0xaddr", 9999999999, 1000000)

    async def test_revoke_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.revoke()

    async def test_record_spend_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.record_spend("0xaddr", 50000)

    async def test_set_spend_recorder_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.set_spend_recorder("0xaddr", True)

    async def test_delegate_by_sig_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.delegate_by_sig("0xagent", "0xdelegate", 9999999999, 1000000, b'\x00')

    async def test_revoke_by_sig_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.revoke_by_sig("0xagent", b'\x00')

    async def test_is_valid_delegation_returns_false(self, contract):
        """When no contract, is_valid_delegation should return False (not raise)."""
        result = await contract.is_valid_delegation("0xagent", "0xdelegate")
        assert result is False

    async def test_get_delegation_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.get_delegation("0xagent")

    async def test_get_nonce_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.get_nonce("0xagent")

    async def test_get_delegation_history_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.get_delegation_history("0xagent")

    async def test_get_remaining_budget_raises_error(self, contract):
        with pytest.raises(ContractNotConfiguredError, match="AgentDelegation"):
            await contract.get_remaining_budget("0xagent")
