"""Unit tests for EventHandlers."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.handlers.event_handlers import EventHandlers
from app.domain.events.base import DomainEvent
from app.domain.events.agent_events import AgentRegistered, AgentDelegated, AgentReputationUpdated
from app.domain.events.billing_events import ResourceConsumed, ResourceConsumedV2, BillingSessionSettled
from app.domain.events.payment_events import PaymentVerified, InvoiceGenerated, InvoicePaid
from app.domain.events.provider_events import (
    ProviderRegistered, ProviderStatusChanged, HealthReported,
    SlashingApplied, ProviderStaked, ProviderUnstaked,
    GPUSpecsUpdated, ProviderJobCompleted,
)


@pytest.fixture
def kafka_producer():
    return AsyncMock()


@pytest.fixture
def handlers(kafka_producer):
    return EventHandlers(kafka_producer=kafka_producer)


@pytest.fixture
def handlers_no_kafka():
    return EventHandlers()


def make_event(event_class, aggregate_id="agg-1", **data):
    """Create an event instance using the correct constructor for each event class."""
    # Provider events (pass-through) - they inherit DomainEvent directly
    if event_class in (ProviderRegistered, ProviderStatusChanged, HealthReported,
                       ProviderStaked, ProviderUnstaked,
                       GPUSpecsUpdated, ProviderJobCompleted):
        return event_class(aggregate_id=aggregate_id, data=data)
    if event_class is SlashingApplied:
        # Ensure all required fields are provided to avoid logging format errors
        data.setdefault("penalty_percent", 10)
        data.setdefault("slashed_amount", 1000)
        data.setdefault("reason", "downtime")
        data.setdefault("new_reputation", 50)
        data.setdefault("remaining_stake", 0)
        return event_class(aggregate_id=aggregate_id, data=data)

    # Agent events
    if event_class is AgentRegistered:
        return AgentRegistered(
            agent_id=data.get("agent_id", aggregate_id),
            owner_address=data.get("owner_address", "0xabc"),
            delegation_address=data.get("delegation_address"),
        )
    if event_class is AgentDelegated:
        return AgentDelegated(
            agent_id=data.get("agent_id", aggregate_id),
            delegate_address=data.get("delegate_address", "0xdef"),
            expires_at=data.get("expires_at", 9999999999),
        )
    if event_class is AgentReputationUpdated:
        return AgentReputationUpdated(
            agent_id=data.get("agent_id", aggregate_id),
            new_score=data.get("new_score", 85),
            reason=data.get("reason", "good behavior"),
        )

    # Billing events
    if event_class is ResourceConsumed:
        return ResourceConsumed(
            session_id=data.get("session_id", aggregate_id),
            agent_id=data.get("agent_id", "agent-1"),
            amount=data.get("amount", 100),
            resource_type=data.get("resource_type", "compute"),
        )
    if event_class is ResourceConsumedV2:
        return ResourceConsumedV2(
            aggregate_id=data.get("aggregate_id", aggregate_id),
            session_id=data.get("session_id", "session-1"),
            agent_id=data.get("agent_id", "agent-1"),
            resource_type=data.get("resource_type", "gpu"),
            amount=data.get("amount", 50),
            cost_micro_usdc=data.get("cost_micro_usdc", 0),
            provider_id=data.get("provider_id", "legacy_system"),
        )
    if event_class is BillingSessionSettled:
        return BillingSessionSettled(
            session_id=data.get("session_id", aggregate_id),
            tx_hash=data.get("tx_hash", "0xtx"),
            amount_paid=data.get("amount_paid", 50000),
        )

    # Payment events
    if event_class is PaymentVerified:
        return PaymentVerified(
            payment_id=data.get("payment_id", aggregate_id),
            tx_hash=data.get("tx_hash", "0xtx"),
            block_number=data.get("block_number", 12345),
        )
    if event_class is InvoiceGenerated:
        return InvoiceGenerated(
            invoice_id=data.get("invoice_id", aggregate_id),
            agent_id=data.get("agent_id", "agent-1"),
            amount=data.get("amount", 1000),
            due_date=data.get("due_date", "2026-07-01"),
        )
    if event_class is InvoicePaid:
        return InvoicePaid(
            invoice_id=data.get("invoice_id", aggregate_id),
            tx_hash=data.get("tx_hash", "0xtx"),
        )

    # Fallback: try generic constructor
    return event_class(aggregate_id=aggregate_id, data=data)


class TestHandleEventRouting:
    """Test that handle_event routes to the correct handler."""

    @pytest.mark.parametrize("event_class,expected_topic", [
        (AgentRegistered, "agent.registered"),
        (AgentDelegated, "agent.delegated"),
        (AgentReputationUpdated, "agent.reputation"),
        (ResourceConsumed, "billing.resource.consumed"),
        (ResourceConsumedV2, "billing.resource.consumed.v2"),
        (BillingSessionSettled, "billing.session.settled"),
        (PaymentVerified, "payment.verified"),
        (InvoiceGenerated, "billing.invoice.generated"),
        (InvoicePaid, "billing.invoice.paid"),
        (ProviderRegistered, "depin.provider.registered"),
        (ProviderStatusChanged, "depin.provider.status"),
        (HealthReported, "depin.provider.health"),
        (SlashingApplied, "depin.provider.slashed"),
        (ProviderStaked, "depin.provider.staked"),
        (ProviderUnstaked, "depin.provider.unstaked"),
        (GPUSpecsUpdated, "depin.provider.gpu_specs"),
        (ProviderJobCompleted, "depin.provider.job"),
    ])
    async def test_routes_to_correct_handler(self, handlers, kafka_producer, event_class, expected_topic):
        event = make_event(event_class)
        await handlers.handle_event(event)
        kafka_producer.publish_event.assert_awaited_once_with(event, expected_topic)

    async def test_unknown_event_type_is_ignored(self, handlers, kafka_producer):
        """Unknown event types should be silently ignored."""
        # Create a class that extends DomainEvent so it can be constructed
        class UnknownEvent(DomainEvent):
            pass
        unknown_event = UnknownEvent(aggregate_id="agg-1", data={})
        await handlers.handle_event(unknown_event)
        kafka_producer.publish_event.assert_not_awaited()


class TestEventHandlersWithoutKafka:
    """Test handlers when no Kafka producer is configured."""

    @pytest.mark.parametrize("event_class", [
        AgentRegistered,
        AgentDelegated,
        AgentReputationUpdated,
        ResourceConsumed,
        ResourceConsumedV2,
        BillingSessionSettled,
        PaymentVerified,
        InvoiceGenerated,
        InvoicePaid,
        ProviderRegistered,
        ProviderStatusChanged,
        HealthReported,
        SlashingApplied,
        ProviderStaked,
        ProviderUnstaked,
        GPUSpecsUpdated,
        ProviderJobCompleted,
    ])
    async def test_handles_event_without_kafka(self, handlers_no_kafka, event_class):
        """Should not raise when Kafka producer is None."""
        event = make_event(event_class)
        await handlers_no_kafka.handle_event(event)
        # No assertion needed - just verifying no exception is raised


class TestAgentEventHandlers:
    """Specific tests for agent event handlers."""

    async def test_on_agent_registered_logs_info(self, handlers, kafka_producer):
        event = make_event(
            AgentRegistered,
            agent_id="agent-1",
            owner_address="0xabc",
            delegation_address="0xdef",
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "agent.registered")
        mock_logger.info.assert_called_once()

    async def test_on_agent_delegated_logs_info(self, handlers, kafka_producer):
        event = make_event(
            AgentDelegated,
            agent_id="agent-1",
            delegate_address="0xdef",
            expires_at=9999999999,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "agent.delegated")
        mock_logger.info.assert_called_once()

    async def test_on_reputation_updated_logs_info(self, handlers, kafka_producer):
        event = make_event(
            AgentReputationUpdated,
            agent_id="agent-1",
            new_score=85,
            reason="good behavior",
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "agent.reputation")
        mock_logger.info.assert_called_once()


class TestBillingEventHandlers:
    """Specific tests for billing event handlers."""

    async def test_on_resource_consumed_v1(self, handlers, kafka_producer):
        event = make_event(
            ResourceConsumed,
            session_id="session-1",
            agent_id="agent-1",
            resource_type="compute",
            amount=100,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "billing.resource.consumed")
        mock_logger.info.assert_called_once()

    async def test_on_resource_consumed_v2_with_provider(self, handlers, kafka_producer):
        event = make_event(
            ResourceConsumedV2,
            aggregate_id="session-1",
            session_id="session-1",
            agent_id="agent-1",
            resource_type="gpu",
            amount=50,
            cost_micro_usdc=10000,
            provider_id="provider-1",
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "billing.resource.consumed.v2")
        mock_logger.info.assert_called_once()

    async def test_on_billing_session_settled(self, handlers, kafka_producer):
        event = make_event(
            BillingSessionSettled,
            session_id="session-1",
            tx_hash="0xtx",
            amount_paid=50000,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "billing.session.settled")
        mock_logger.info.assert_called_once()


class TestPaymentEventHandlers:
    """Specific tests for payment event handlers."""

    async def test_on_payment_verified(self, handlers, kafka_producer):
        event = make_event(
            PaymentVerified,
            payment_id="pay-1",
            tx_hash="0xtx",
            block_number=12345,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "payment.verified")
        mock_logger.info.assert_called_once()

    async def test_on_invoice_generated(self, handlers, kafka_producer):
        event = make_event(
            InvoiceGenerated,
            invoice_id="inv-1",
            agent_id="agent-1",
            amount=1000,
            due_date="2026-07-01",
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "billing.invoice.generated")
        mock_logger.info.assert_called_once()

    async def test_on_invoice_paid(self, handlers, kafka_producer):
        event = make_event(
            InvoicePaid,
            invoice_id="inv-1",
            tx_hash="0xtx",
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "billing.invoice.paid")
        mock_logger.info.assert_called_once()


class TestProviderEventHandlers:
    """Specific tests for provider (DePIN) event handlers."""

    async def test_on_provider_registered(self, handlers, kafka_producer):
        event = make_event(
            ProviderRegistered,
            owner_address="0xabc",
            gpu_specs={"model": "RTX 4090", "tflops_fp16": 82.6, "vram_gb": 24},
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.registered")
        mock_logger.info.assert_called_once()

    async def test_on_provider_status_changed(self, handlers, kafka_producer):
        event = make_event(
            ProviderStatusChanged,
            old_status="pending",
            new_status="active",
            reason="stake confirmed",
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.status")
        mock_logger.info.assert_called_once()

    async def test_on_health_reported(self, handlers, kafka_producer):
        event = make_event(
            HealthReported,
            is_online=True,
            uptime_seconds=3600,
            total_uptime_seconds=7200,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.health")
        mock_logger.info.assert_called_once()

    async def test_on_slashing_applied(self, handlers, kafka_producer):
        event = make_event(
            SlashingApplied,
            penalty_percent=10,
            slashed_amount=1000,
            reason="downtime",
            new_reputation=50,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.slashed")
        mock_logger.warning.assert_called_once()

    async def test_on_provider_staked(self, handlers, kafka_producer):
        event = make_event(
            ProviderStaked,
            amount=50000,
            total_staked=150000,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.staked")
        mock_logger.info.assert_called_once()

    async def test_on_provider_unstaked(self, handlers, kafka_producer):
        event = make_event(
            ProviderUnstaked,
            amount=25000,
            total_staked=125000,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.unstaked")
        mock_logger.info.assert_called_once()

    async def test_on_gpu_specs_updated(self, handlers, kafka_producer):
        event = make_event(
            GPUSpecsUpdated,
            new_specs={"model": "RTX 5090", "tflops_fp16": 120.0, "vram_gb": 32},
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.gpu_specs")
        mock_logger.info.assert_called_once()

    async def test_on_provider_job_completed(self, handlers, kafka_producer):
        event = make_event(
            ProviderJobCompleted,
            session_id="session-1",
            agent_id="agent-1",
            success=True,
            compute_time_seconds=120,
        )
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await handlers.handle_event(event)

        kafka_producer.publish_event.assert_awaited_once_with(event, "depin.provider.job")
        mock_logger.info.assert_called_once()
