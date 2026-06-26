"""Unit tests for CommandHandlers."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.handlers.command_handlers import CommandHandlers
from app.application.commands.register_agent import (
    RegisterAgentCommand,
    DelegateAgentCommand,
    RevokeDelegationCommand,
    UpdateReputationCommand,
)
from app.application.commands.consume_resource import ConsumeResourceCommand
from app.application.commands.settle_invoice import SettleInvoiceCommand
from app.core.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    InvoiceNotFoundError,
    InvoiceAlreadySettledError,
)
from app.domain.events.agent_events import AgentRegistered, AgentDelegated
from app.domain.events.billing_events import BillingSessionStarted, ResourceConsumedV2
from app.domain.events.payment_events import InvoiceGenerated, InvoicePaid


@pytest.fixture
def event_store():
    store = MagicMock()
    store.load_stream = AsyncMock(return_value=[])
    store.append_events = AsyncMock()
    return store


@pytest.fixture
def handlers(event_store):
    return CommandHandlers(event_store)


# =========================================================================
# Test: handle_register_agent
# =========================================================================


class TestHandleRegisterAgent:
    @pytest.mark.asyncio
    async def test_register_agent_success(self, handlers, event_store):
        command = RegisterAgentCommand(
            agent_id="agent-1",
            owner_address="0x1234",
        )
        await handlers.handle_register_agent(command)
        event_store.append_events.assert_awaited_once()
        call_args = event_store.append_events.await_args
        assert call_args[0][0] == "agent-1"  # stream_id
        assert len(call_args[0][1]) == 1  # one event
        assert isinstance(call_args[0][1][0], AgentRegistered)
        assert call_args.kwargs["expected_version"] == 0

    @pytest.mark.asyncio
    async def test_register_agent_already_exists(self, handlers, event_store):
        event_store.load_stream.return_value = [MagicMock()]
        command = RegisterAgentCommand(
            agent_id="agent-1",
            owner_address="0x1234",
        )
        with pytest.raises(AgentAlreadyExistsError):
            await handlers.handle_register_agent(command)

    @pytest.mark.asyncio
    async def test_register_agent_with_delegation(self, handlers, event_store):
        command = RegisterAgentCommand(
            agent_id="agent-1",
            owner_address="0x1234",
            delegation_address="0xdeleg",
        )
        await handlers.handle_register_agent(command)
        call_args = event_store.append_events.await_args
        assert call_args[0][1][0].data.get("delegation_address") == "0xdeleg"


# =========================================================================
# Test: handle_delegate_agent
# =========================================================================


class TestHandleDelegateAgent:
    @pytest.mark.asyncio
    async def test_delegate_agent_success(self, handlers, event_store):
        event_store.load_stream.return_value = [
            AgentRegistered("agent-1", "0x1234"),
        ]
        command = DelegateAgentCommand(
            agent_id="agent-1",
            delegate_address="0xdeleg",
            expires_at="2027-01-01",
        )
        await handlers.handle_delegate_agent(command)
        event_store.append_events.assert_awaited_once()
        call_args = event_store.append_events.await_args
        assert len(call_args[0][1]) == 1
        assert isinstance(call_args[0][1][0], AgentDelegated)

    @pytest.mark.asyncio
    async def test_delegate_agent_not_found(self, handlers, event_store):
        event_store.load_stream.return_value = []
        command = DelegateAgentCommand(
            agent_id="agent-unknown",
            delegate_address="0xdeleg",
            expires_at="2027-01-01",
        )
        with pytest.raises(AgentNotFoundError):
            await handlers.handle_delegate_agent(command)


# =========================================================================
# Test: handle_revoke_delegation
# =========================================================================


class TestHandleRevokeDelegation:
    @pytest.mark.asyncio
    async def test_revoke_delegation_success(self, handlers, event_store):
        event_store.load_stream.return_value = [
            AgentRegistered("agent-1", "0x1234"),
            AgentDelegated("agent-1", "0xdeleg", "2027-01-01"),
        ]
        command = RevokeDelegationCommand(agent_id="agent-1")
        await handlers.handle_revoke_delegation(command)
        event_store.append_events.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_revoke_delegation_not_found(self, handlers, event_store):
        event_store.load_stream.return_value = []
        command = RevokeDelegationCommand(agent_id="agent-unknown")
        with pytest.raises(AgentNotFoundError):
            await handlers.handle_revoke_delegation(command)


# =========================================================================
# Test: handle_update_reputation
# =========================================================================


class TestHandleUpdateReputation:
    @pytest.mark.asyncio
    async def test_update_reputation_success(self, handlers, event_store):
        event_store.load_stream.return_value = [
            AgentRegistered("agent-1", "0x1234"),
        ]
        command = UpdateReputationCommand(
            agent_id="agent-1",
            new_score=85,
            reason="good_performance",
        )
        await handlers.handle_update_reputation(command)
        event_store.append_events.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_reputation_not_found(self, handlers, event_store):
        event_store.load_stream.return_value = []
        command = UpdateReputationCommand(
            agent_id="agent-unknown",
            new_score=50,
            reason="test",
        )
        with pytest.raises(AgentNotFoundError):
            await handlers.handle_update_reputation(command)


# =========================================================================
# Test: handle_consume_resource
# =========================================================================


class TestHandleConsumeResource:
    @pytest.mark.asyncio
    async def test_consume_resource_success(self, handlers, event_store):
        command = ConsumeResourceCommand(
            agent_id="agent-1",
            resource_type="tflops",
            amount=100,
            x402_payment={"verified": True},
        )
        session_id = await handlers.handle_consume_resource(command)
        assert session_id.startswith("session:agent-1:")
        event_store.append_events.assert_awaited_once()
        call_args = event_store.append_events.await_args
        assert len(call_args[0][1]) == 2  # start + record_consumption
        assert isinstance(call_args[0][1][0], BillingSessionStarted)
        assert isinstance(call_args[0][1][1], ResourceConsumedV2)

    @pytest.mark.asyncio
    async def test_consume_resource_without_verification(self, handlers, event_store):
        command = ConsumeResourceCommand(
            agent_id="agent-1",
            resource_type="tflops",
            amount=100,
            x402_payment={"verified": False},
        )
        session_id = await handlers.handle_consume_resource(command)
        assert session_id is not None
        event_store.append_events.assert_awaited_once()


# =========================================================================
# Test: handle_settle_invoice
# =========================================================================


class TestHandleSettleInvoice:
    @pytest.mark.asyncio
    async def test_settle_invoice_success(self, handlers, event_store):
        event_store.load_stream.return_value = [
            InvoiceGenerated("inv-1", "agent-1", 100_000, "2026-07-01"),
        ]
        command = SettleInvoiceCommand(invoice_id="inv-1", agent_id="agent-1")
        await handlers.handle_settle_invoice(command)
        event_store.append_events.assert_awaited_once()
        call_args = event_store.append_events.await_args
        assert len(call_args[0][1]) == 1
        assert isinstance(call_args[0][1][0], InvoicePaid)

    @pytest.mark.asyncio
    async def test_settle_invoice_not_found(self, handlers, event_store):
        event_store.load_stream.return_value = []
        command = SettleInvoiceCommand(invoice_id="inv-unknown", agent_id="agent-1")
        with pytest.raises(InvoiceNotFoundError):
            await handlers.handle_settle_invoice(command)

    @pytest.mark.asyncio
    async def test_settle_invoice_already_settled(self, handlers, event_store):
        event_store.load_stream.return_value = [
            InvoiceGenerated("inv-1", "agent-1", 100_000, "2026-07-01"),
            InvoicePaid("inv-1", "0xabc"),
        ]
        command = SettleInvoiceCommand(invoice_id="inv-1", agent_id="agent-1")
        with pytest.raises(InvoiceAlreadySettledError):
            await handlers.handle_settle_invoice(command)
