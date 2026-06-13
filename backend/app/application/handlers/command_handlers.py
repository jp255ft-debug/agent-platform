"""Command handlers - process commands and produce events."""
from uuid import uuid4
from app.domain.aggregates.agent import AgentAggregate
from app.domain.aggregates.billing_session import BillingSessionAggregate
from app.domain.aggregates.invoice import InvoiceAggregate
from app.domain.repositories.event_store import EventStore
from app.application.commands.register_agent import (
    RegisterAgentCommand, DelegateAgentCommand, RevokeDelegationCommand, UpdateReputationCommand,
)
from app.application.commands.consume_resource import ConsumeResourceCommand
from app.application.commands.settle_invoice import SettleInvoiceCommand


class CommandHandlers:
    def __init__(self, event_store: EventStore):
        self._event_store = event_store

    async def handle_register_agent(self, command: RegisterAgentCommand) -> None:
        """Handle agent registration."""
        # Check if agent already exists
        existing = await self._event_store.load_stream(command.agent_id)
        if existing:
            raise ValueError(f"Agent {command.agent_id} already exists")

        aggregate = AgentAggregate.register(
            command.agent_id, command.owner_address, command.delegation_address,
        )
        await self._event_store.append_events(
            command.agent_id, aggregate.get_changes(), expected_version=0,
        )

    async def handle_delegate_agent(self, command: DelegateAgentCommand) -> None:
        """Handle agent delegation (EIP-7702)."""
        events = await self._event_store.load_stream(command.agent_id)
        if not events:
            raise ValueError(f"Agent {command.agent_id} not found")

        aggregate = AgentAggregate(command.agent_id)
        for event in events:
            aggregate._apply(event)

        aggregate.delegate(command.delegate_address, command.expires_at)
        await self._event_store.append_events(
            command.agent_id, aggregate.get_changes(),
            expected_version=aggregate.version - len(aggregate.get_changes()),
        )

    async def handle_revoke_delegation(self, command: RevokeDelegationCommand) -> None:
        """Handle delegation revocation."""
        events = await self._event_store.load_stream(command.agent_id)
        if not events:
            raise ValueError(f"Agent {command.agent_id} not found")

        aggregate = AgentAggregate(command.agent_id)
        for event in events:
            aggregate._apply(event)

        aggregate.revoke_delegation()
        await self._event_store.append_events(
            command.agent_id, aggregate.get_changes(),
            expected_version=aggregate.version - len(aggregate.get_changes()),
        )

    async def handle_update_reputation(self, command: UpdateReputationCommand) -> None:
        """Handle reputation update."""
        events = await self._event_store.load_stream(command.agent_id)
        if not events:
            raise ValueError(f"Agent {command.agent_id} not found")

        aggregate = AgentAggregate(command.agent_id)
        for event in events:
            aggregate._apply(event)

        aggregate.update_reputation(command.new_score, command.reason)
        await self._event_store.append_events(
            command.agent_id, aggregate.get_changes(),
            expected_version=aggregate.version - len(aggregate.get_changes()),
        )

    async def handle_consume_resource(self, command: ConsumeResourceCommand) -> str:
        """Handle resource consumption with x402 payment."""
        # Verify x402 payment
        if not command.x402_payment.get("verified", False):
            # In production, verify the payment on-chain here
            pass

        # Create or load billing session
        session_id = f"session:{command.agent_id}:{uuid4().hex[:8]}"
        session = BillingSessionAggregate.start(
            session_id, command.agent_id, command.resource_type,
        )
        session.record_consumption(command.amount)

        await self._event_store.append_events(
            session_id, session.get_changes(), expected_version=0,
        )
        return session_id

    async def handle_settle_invoice(self, command: SettleInvoiceCommand) -> None:
        """Handle invoice settlement."""
        events = await self._event_store.load_stream(command.invoice_id)
        if not events:
            raise ValueError(f"Invoice {command.invoice_id} not found")

        aggregate = InvoiceAggregate(command.invoice_id)
        for event in events:
            aggregate._apply(event)

        if aggregate.status != "pending":
            raise ValueError(f"Invoice {command.invoice_id} is already {aggregate.status}")

        aggregate.pay(tx_hash=f"0x{uuid4().hex}")
        await self._event_store.append_events(
            command.invoice_id, aggregate.get_changes(),
            expected_version=aggregate.version - len(aggregate.get_changes()),
        )
