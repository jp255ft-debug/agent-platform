"""Unit tests for BillingSessionAggregate."""
import pytest

from app.domain.aggregates.billing_session import BillingSessionAggregate
from app.domain.events.billing_events import (
    BillingSessionStarted,
    ResourceConsumed,
    ResourceConsumedV2,
    BillingSessionClosed,
    BillingSessionSettled,
)


class TestBillingSessionStart:
    def test_start_creates_active_session(self):
        session = BillingSessionAggregate.start(
            session_id="session-1",
            agent_id="agent-1",
            resource_type="tflops",
        )
        assert session.session_id == "session-1"
        assert session.agent_id == "agent-1"
        assert session.resource_type == "tflops"
        assert session.status == "active"
        assert session.total_consumed == 0
        assert session.total_cost_micro_usdc == 0

    def test_start_with_provider_id(self):
        session = BillingSessionAggregate.start(
            session_id="session-1",
            agent_id="agent-1",
            resource_type="tflops",
            provider_id="provider-1",
        )
        assert session.provider_id == "provider-1"

    def test_start_emits_billing_session_started_event(self):
        session = BillingSessionAggregate.start(
            session_id="session-1",
            agent_id="agent-1",
            resource_type="tflops",
        )
        changes = session.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], BillingSessionStarted)
        assert changes[0].data["agent_id"] == "agent-1"
        assert changes[0].data["resource_type"] == "tflops"


class TestRecordConsumption:
    def test_record_consumption_v2_increases_total(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.record_consumption(amount=100, cost_micro_usdc=50_000)
        assert session.total_consumed == 100
        assert session.total_cost_micro_usdc == 50_000

    def test_record_consumption_v2_emits_resource_consumed_v2(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.record_consumption(amount=100, cost_micro_usdc=50_000)
        changes = session.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], ResourceConsumedV2)
        assert changes[0].data["amount"] == 100
        assert changes[0].data["cost_micro_usdc"] == 50_000

    def test_record_consumption_with_provider_id(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.record_consumption(amount=100, cost_micro_usdc=50_000, provider_id="provider-1")
        changes = session.get_changes()
        assert changes[0].data["provider_id"] == "provider-1"

    def test_record_consumption_default_provider_is_legacy(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.record_consumption(amount=100)
        changes = session.get_changes()
        assert changes[0].data["provider_id"] == "legacy_system"

    def test_record_consumption_accumulates_multiple_calls(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.record_consumption(amount=50, cost_micro_usdc=25_000)
        session.record_consumption(amount=30, cost_micro_usdc=15_000)
        assert session.total_consumed == 80
        assert session.total_cost_micro_usdc == 40_000


class TestCloseSession:
    def test_close_sets_status_to_closed(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.close()
        assert session.status == "closed"

    def test_close_emits_billing_session_closed_event(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.record_consumption(amount=100)
        session.close()
        changes = session.get_changes()
        assert len(changes) == 2
        assert isinstance(changes[1], BillingSessionClosed)
        assert changes[1].data["total_consumed"] == 100


class TestSettleSession:
    def test_settle_sets_status_to_settled(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.settle(tx_hash="0xabc", amount_paid=100_000)
        assert session.status == "settled"

    def test_settle_emits_billing_session_settled_event(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        session.settle(tx_hash="0xabc", amount_paid=100_000)
        changes = session.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], BillingSessionSettled)
        assert changes[0].data["tx_hash"] == "0xabc"
        assert changes[0].data["amount_paid"] == 100_000


class TestBillingSessionEventSourcing:
    def test_rebuild_from_v1_events(self):
        """Test that legacy V1 events are accepted for reconstruction."""
        session = BillingSessionAggregate(session_id="session-1")
        event1 = BillingSessionStarted(
            session_id="session-1", agent_id="agent-1", resource_type="tflops",
        )
        event2 = ResourceConsumed(
            session_id="session-1", agent_id="agent-1", amount=50, resource_type="tflops",
        )
        event3 = ResourceConsumedV2(
            aggregate_id="session-1",
            session_id="session-1",
            agent_id="agent-1",
            resource_type="tflops",
            amount=100,
            cost_micro_usdc=50_000,
            provider_id="provider-1",
        )
        session._apply(event1)
        session._apply(event2)
        session._apply(event3)
        assert session.agent_id == "agent-1"
        assert session.resource_type == "tflops"
        assert session.total_consumed == 150  # 50 (V1) + 100 (V2)
        assert session.total_cost_micro_usdc == 50_000
        assert session.provider_id == "provider-1"
        assert session.version == 3

    def test_get_changes_returns_copy(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        changes = session.get_changes()
        assert len(changes) == 1
        changes.clear()
        assert len(session.get_changes()) == 1

    def test_clear_changes_empties_list(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        session.clear_changes()
        assert len(session.get_changes()) == 0

    def test_version_increments(self):
        session = BillingSessionAggregate.start("s1", "a1", "tflops")
        assert session.version == 1
        session.record_consumption(amount=100)
        assert session.version == 2
        session.close()
        assert session.version == 3
