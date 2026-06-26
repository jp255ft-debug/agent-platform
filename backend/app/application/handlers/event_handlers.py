"""Event handlers - react to domain events for side effects.

Handles both legacy (V1) and DePIN (V2) events for backward compatibility.
"""
from app.domain.events.base import DomainEvent
from app.domain.events.agent_events import AgentRegistered, AgentDelegated, AgentReputationUpdated
from app.domain.events.billing_events import ResourceConsumed, ResourceConsumedV2, BillingSessionSettled
from app.domain.events.payment_events import PaymentVerified, InvoiceGenerated, InvoicePaid
from app.domain.events.provider_events import (
    ProviderRegistered, ProviderStatusChanged, HealthReported,
    SlashingApplied, ProviderStaked, ProviderUnstaked,
    GPUSpecsUpdated, ProviderJobCompleted,
)


class EventHandlers:
    """Handles side effects for domain events.

    Suporta eventos legados (V1) e DePIN (V2) para retrocompatibilidade.
    """

    def __init__(self, kafka_producer=None, web3_client=None):
        self._kafka_producer = kafka_producer
        self._web3_client = web3_client

    async def handle_event(self, event: DomainEvent) -> None:
        """Route event to the appropriate handler."""
        handlers = {
            # Agent events
            AgentRegistered: self._on_agent_registered,
            AgentDelegated: self._on_agent_delegated,
            AgentReputationUpdated: self._on_reputation_updated,
            # Billing events (V1 legacy + V2 DePIN)
            ResourceConsumed: self._on_resource_consumed,
            ResourceConsumedV2: self._on_resource_consumed_v2,
            BillingSessionSettled: self._on_billing_session_settled,
            # Payment events
            PaymentVerified: self._on_payment_verified,
            InvoiceGenerated: self._on_invoice_generated,
            InvoicePaid: self._on_invoice_paid,
            # Provider events (DePIN)
            ProviderRegistered: self._on_provider_registered,
            ProviderStatusChanged: self._on_provider_status_changed,
            HealthReported: self._on_health_reported,
            SlashingApplied: self._on_slashing_applied,
            ProviderStaked: self._on_provider_staked,
            ProviderUnstaked: self._on_provider_unstaked,
            GPUSpecsUpdated: self._on_gpu_specs_updated,
            ProviderJobCompleted: self._on_provider_job_completed,
        }
        handler = handlers.get(type(event))
        if handler:
            await handler(event)

    # =========================================================================
    # Agent Event Handlers
    # =========================================================================

    async def _on_agent_registered(self, event: AgentRegistered) -> None:
        """Handle agent registered event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "agent.registered")

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

    # =========================================================================
    # Billing Event Handlers (V1 Legacy)
    # =========================================================================

    async def _on_resource_consumed(self, event: ResourceConsumed) -> None:
        """Handle legacy V1 resource consumed event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "billing.resource.consumed")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Resource consumed (V1): agent=%s type=%s amount=%d",
            event.data.get("agent_id"),
            event.data.get("resource_type"),
            event.data.get("amount"),
        )

    async def _on_resource_consumed_v2(self, event: ResourceConsumedV2) -> None:
        """Handle DePIN V2 resource consumed event with cost and provider."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "billing.resource.consumed.v2")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Resource consumed (V2/DePIN): agent=%s type=%s amount=%d "
            "cost_micro_usdc=%d provider=%s",
            event.data.get("agent_id"),
            event.data.get("resource_type"),
            event.data.get("amount"),
            event.data.get("cost_micro_usdc", 0),
            event.data.get("provider_id", "unknown"),
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

    # =========================================================================
    # Payment Event Handlers
    # =========================================================================

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

    # =========================================================================
    # Provider Event Handlers (DePIN)
    # =========================================================================

    async def _on_provider_registered(self, event: ProviderRegistered) -> None:
        """Handle provider registered event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.registered")

        import logging
        logger = logging.getLogger(__name__)
        specs = event.data.get("gpu_specs", {})
        logger.info(
            "Provider registered: %s (owner: %s, GPU: %s, TFLOPS: %.1f)",
            event.aggregate_id,
            event.data.get("owner_address"),
            specs.get("model", "unknown"),
            specs.get("tflops_fp16", 0.0),
        )

    async def _on_provider_status_changed(self, event: ProviderStatusChanged) -> None:
        """Handle provider status changed event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.status")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Provider status changed: %s %s -> %s (reason: %s)",
            event.aggregate_id,
            event.data.get("old_status"),
            event.data.get("new_status"),
            event.data.get("reason"),
        )

    async def _on_health_reported(self, event: HealthReported) -> None:
        """Handle health report event from node telemetry."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.health")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Health report: %s online=%s uptime=%ds total=%ds",
            event.aggregate_id,
            event.data.get("is_online"),
            event.data.get("uptime_seconds", 0),
            event.data.get("total_uptime_seconds", 0),
        )

    async def _on_slashing_applied(self, event: SlashingApplied) -> None:
        """Handle slashing applied event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.slashed")

        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "SLASHING: %s penalty=%d%% amount=%d reason=%s rep=%d",
            event.aggregate_id,
            event.data.get("penalty_percent"),
            event.data.get("slashed_amount", 0),
            event.data.get("reason"),
            event.data.get("new_reputation", 0),
        )

    async def _on_provider_staked(self, event: ProviderStaked) -> None:
        """Handle provider staked event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.staked")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Provider staked: %s +%d total=%d",
            event.aggregate_id,
            event.data.get("amount", 0),
            event.data.get("total_staked", 0),
        )

    async def _on_provider_unstaked(self, event: ProviderUnstaked) -> None:
        """Handle provider unstaked event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.unstaked")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Provider unstaked: %s -%d total=%d",
            event.aggregate_id,
            event.data.get("amount", 0),
            event.data.get("total_staked", 0),
        )

    async def _on_gpu_specs_updated(self, event: GPUSpecsUpdated) -> None:
        """Handle GPU specs updated event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.gpu_specs")

        import logging
        logger = logging.getLogger(__name__)
        new_specs = event.data.get("new_specs", {})
        logger.info(
            "GPU specs updated: %s -> %s (TFLOPS: %.1f, VRAM: %dGB)",
            event.aggregate_id,
            new_specs.get("model", "unknown"),
            new_specs.get("tflops_fp16", 0.0),
            new_specs.get("vram_gb", 0),
        )

    async def _on_provider_job_completed(self, event: ProviderJobCompleted) -> None:
        """Handle provider job completed event."""
        if self._kafka_producer:
            await self._kafka_producer.publish_event(event, "depin.provider.job")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "Job completed: provider=%s session=%s agent=%s success=%s time=%ds",
            event.aggregate_id,
            event.data.get("session_id"),
            event.data.get("agent_id"),
            event.data.get("success"),
            event.data.get("compute_time_seconds", 0),
        )


