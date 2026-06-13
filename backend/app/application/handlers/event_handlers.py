"""Event handlers - react to domain events for side effects."""
from app.domain.events.base import DomainEvent
from app.domain.events.agent_events import AgentRegistered, AgentDelegated, AgentReputationUpdated
from app.domain.events.billing_events import ResourceConsumed, BillingSessionSettled
from app.domain.events.payment_events import PaymentVerified, InvoiceGenerated, InvoicePaid


class EventHandlers:
    """Handles side effects for domain events."""

    def __init__(self, kafka_producer=None, web3_client=None):
        self._kafka_producer = kafka_producer
        self._web3_client = web3_client

    async def handle_event(self, event: DomainEvent) -> None:
        """Route event to the appropriate handler."""
        handlers = {
            AgentRegistered: self._on_agent_registered,
            AgentDelegated: self._on_agent_delegated,
            AgentReputationUpdated: self._on_reputation_updated,
            ResourceConsumed: self._on_resource_consumed,
            BillingSessionSettled: self._on_billing_session_settled,
            PaymentVerified: self._on_payment_verified,
            InvoiceGenerated: self._on_invoice_generated,
            InvoicePaid: self._on_invoice_paid,
        }
        handler = handlers.get(type(event))
        if handler:
            await handler(event)

    async def _on_agent_registered(self, event: AgentRegistered) -> None:
        """Handle agent registered event."""
        # Publish to Kafka for downstream services
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "agent.registered")

        # Log registration
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Agent registered: %s (owner: %s, delegation: %s)",
            event.data.get("agent_id"),
            event.data.get("owner_address"),
            event.data.get("delegation_address"),
        )

    async def _on_agent_delegated(self, event: AgentDelegated) -> None:
        """Handle agent delegated event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "agent.delegated")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Agent delegated: %s -> %s (expires: %s)",
            event.data.get("agent_id"),
            event.data.get("delegate_address"),
            event.data.get("expires_at"),
        )

    async def _on_reputation_updated(self, event: AgentReputationUpdated) -> None:
        """Handle reputation updated event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "agent.reputation")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Reputation updated: %s -> %d (reason: %s)",
            event.data.get("agent_id"),
            event.data.get("new_score"),
            event.data.get("reason"),
        )

    async def _on_resource_consumed(self, event: ResourceConsumed) -> None:
        """Handle resource consumed event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "billing.resource.consumed")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Resource consumed: agent=%s type=%s amount=%d",
            event.data.get("agent_id"),
            event.data.get("resource_type"),
            event.data.get("amount"),
        )

    async def _on_billing_session_settled(self, event: BillingSessionSettled) -> None:
        """Handle billing session settled event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "billing.session.settled")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Billing session settled: %s (tx: %s, amount: %d)",
            event.data.get("session_id"),
            event.data.get("tx_hash"),
            event.data.get("amount_paid"),
        )

    async def _on_payment_verified(self, event: PaymentVerified) -> None:
        """Handle payment verified event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "payment.verified")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Payment verified: %s (tx: %s, block: %d)",
            event.data.get("payment_id"),
            event.data.get("tx_hash"),
            event.data.get("block_number"),
        )

    async def _on_invoice_generated(self, event: InvoiceGenerated) -> None:
        """Handle invoice generated event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "billing.invoice.generated")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Invoice generated: %s (agent: %s, amount: %d, due: %s)",
            event.data.get("invoice_id"),
            event.data.get("agent_id"),
            event.data.get("amount"),
            event.data.get("due_date"),
        )

    async def _on_invoice_paid(self, event: InvoicePaid) -> None:
        """Handle invoice paid event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "billing.invoice.paid")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Invoice paid: %s (tx: %s)",
            event.data.get("invoice_id"),
            event.data.get("tx_hash"),
        )
