"""Unit tests for GPULeaseAggregate."""
import pytest
from datetime import datetime, timezone, timedelta

from app.domain.aggregates.gpu_lease import GPULeaseAggregate, LeaseStatus
from app.domain.events.gpu_events import (
    GPULeaseRequested,
    GPULeaseProvisioned,
    GPULeaseActivated,
    GPULeaseExtended,
    GPULeaseTerminated,
    GPULeaseExpired,
)


class TestGPULeaseRequest:
    def test_request_creates_lease(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=2,
            vram_gb=24,
            duration_hours=4,
        )
        assert lease.lease_id == "lease-1"
        assert lease.agent_id == "agent-1"
        assert lease.hardware_id == "hw-1"
        assert lease.gpu_model == "RTX 4090"
        assert lease.gpu_count == 2
        assert lease.vram_gb == 24
        assert lease.duration_hours == 4
        assert lease.status == LeaseStatus.REQUESTED
        assert lease.deployment_id is None
        assert lease.total_cost_usdc == 0.0
        assert lease.version == 1

    def test_request_generates_event(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        changes = lease.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], GPULeaseRequested)
        assert changes[0].aggregate_id == "lease-1"
        assert changes[0].data["agent_id"] == "agent-1"
        assert changes[0].data["hardware_id"] == "hw-1"
        assert changes[0].data["gpu_model"] == "RTX 4090"
        assert changes[0].data["gpu_count"] == 1
        assert changes[0].data["duration_hours"] == 2

    def test_request_sets_created_at(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        assert lease.created_at is not None
        assert lease.created_at.tzinfo is not None


class TestGPULeaseProvision:
    def test_provision_updates_lease(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=2,
            vram_gb=24,
            duration_hours=4,
        )
        lease.provision(
            deployment_id="dep-1",
            total_cost_usdc=50.0,
            ionet_fee_usdc=5.0,
        )
        assert lease.deployment_id == "dep-1"
        assert lease.total_cost_usdc == 50.0
        assert lease.ionet_fee_usdc == 5.0
        assert lease.status == LeaseStatus.PROVISIONING
        assert lease.version == 2

    def test_provision_generates_event(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.provision(deployment_id="dep-1", total_cost_usdc=25.0, ionet_fee_usdc=2.5)
        changes = lease.get_changes()
        assert len(changes) == 2  # request + provision
        assert isinstance(changes[1], GPULeaseProvisioned)
        assert changes[1].data["deployment_id"] == "dep-1"
        assert changes[1].data["total_cost_usdc"] == 25.0

    def test_provision_wrong_status_raises(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.provision(deployment_id="dep-1", total_cost_usdc=25.0, ionet_fee_usdc=2.5)
        with pytest.raises(ValueError, match="Cannot provision lease in status provisioning"):
            lease.provision(deployment_id="dep-2", total_cost_usdc=30.0, ionet_fee_usdc=3.0)


class TestGPULeaseActivate:
    def test_activate_sets_active_status(self):
        lease = self._make_provisioned_lease()
        lease.activate()
        assert lease.status == LeaseStatus.ACTIVE
        assert lease.activated_at is not None
        assert lease.expires_at is not None
        assert lease.version == 3

    def test_activate_sets_expiry_correctly(self):
        lease = self._make_provisioned_lease(duration_hours=4)
        before = datetime.now(timezone.utc)
        lease.activate()
        after = datetime.now(timezone.utc)
        assert before <= lease.activated_at <= after
        expected_expiry = lease.activated_at + timedelta(hours=4)
        assert abs((lease.expires_at - expected_expiry).total_seconds()) < 1

    def test_activate_generates_event(self):
        lease = self._make_provisioned_lease()
        lease.activate()
        changes = lease.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], GPULeaseActivated)
        assert "activated_at" in changes[0].data
        assert "expires_at" in changes[0].data

    def test_activate_wrong_status_raises(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        with pytest.raises(ValueError, match="Cannot activate lease in status requested"):
            lease.activate()

    @staticmethod
    def _make_provisioned_lease(duration_hours: int = 2):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=duration_hours,
        )
        lease.clear_changes()
        lease.provision(deployment_id="dep-1", total_cost_usdc=25.0, ionet_fee_usdc=2.5)
        lease.clear_changes()
        return lease


class TestGPULeaseExtend:
    def test_extend_increases_duration(self):
        lease = self._make_active_lease(duration_hours=2)
        lease.extend(additional_hours=3)
        assert lease.duration_hours == 5
        assert lease.status == LeaseStatus.EXTENDING
        assert lease.version == 4

    def test_extend_updates_expiry(self):
        lease = self._make_active_lease(duration_hours=2)
        original_expiry = lease.expires_at
        lease.extend(additional_hours=3)
        expected_expiry = original_expiry + timedelta(hours=3)
        assert abs((lease.expires_at - expected_expiry).total_seconds()) < 1

    def test_extend_generates_event(self):
        lease = self._make_active_lease()
        lease.extend(additional_hours=2)
        changes = lease.get_changes()
        assert isinstance(changes[0], GPULeaseExtended)
        assert changes[0].data["additional_hours"] == 2
        assert changes[0].data["new_duration_hours"] == 4  # 2 + 2

    def test_extend_wrong_status_raises(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        with pytest.raises(ValueError, match="Cannot extend lease in status requested"):
            lease.extend(additional_hours=1)

    @staticmethod
    def _make_active_lease(duration_hours: int = 2):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=duration_hours,
        )
        lease.clear_changes()
        lease.provision(deployment_id="dep-1", total_cost_usdc=25.0, ionet_fee_usdc=2.5)
        lease.clear_changes()
        lease.activate()
        lease.clear_changes()
        return lease


class TestGPULeaseTerminate:
    def test_terminate_sets_terminated_status(self):
        lease = self._make_active_lease()
        lease.terminate(reason="kill_switch")
        assert lease.status == LeaseStatus.TERMINATED
        assert lease.terminated_at is not None
        assert lease.version == 4

    def test_terminate_generates_event(self):
        lease = self._make_active_lease()
        lease.terminate(reason="budget_exceeded")
        changes = lease.get_changes()
        assert isinstance(changes[0], GPULeaseTerminated)
        assert changes[0].data["reason"] == "budget_exceeded"

    def test_terminate_idempotent(self):
        lease = self._make_active_lease()
        lease.terminate(reason="kill_switch")
        version_before = lease.version
        lease.terminate(reason="kill_switch")  # should not raise
        assert lease.version == version_before  # no new event

    def test_terminate_from_requested(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.terminate(reason="cancelled")
        assert lease.status == LeaseStatus.TERMINATED

    @staticmethod
    def _make_active_lease():
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.clear_changes()
        lease.provision(deployment_id="dep-1", total_cost_usdc=25.0, ionet_fee_usdc=2.5)
        lease.clear_changes()
        lease.activate()
        lease.clear_changes()
        return lease


class TestGPULeaseExpire:
    def test_expire_sets_expired_status(self):
        lease = self._make_active_lease()
        lease.expire()
        assert lease.status == LeaseStatus.EXPIRED
        assert lease.version == 4

    def test_expire_generates_event(self):
        lease = self._make_active_lease()
        lease.expire()
        changes = lease.get_changes()
        assert isinstance(changes[0], GPULeaseExpired)

    def test_expire_idempotent(self):
        lease = self._make_active_lease()
        lease.expire()
        version_before = lease.version
        lease.expire()  # should not raise
        assert lease.version == version_before

    def test_expire_wrong_status_noop(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.expire()  # should not raise, but also not change status
        assert lease.status == LeaseStatus.REQUESTED

    @staticmethod
    def _make_active_lease():
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.clear_changes()
        lease.provision(deployment_id="dep-1", total_cost_usdc=25.0, ionet_fee_usdc=2.5)
        lease.clear_changes()
        lease.activate()
        lease.clear_changes()
        return lease


class TestGPULeaseRebuild:
    def test_rebuild_from_events(self):
        """Test rebuilding aggregate state from a sequence of events."""
        from app.domain.events.base import DomainEvent

        events = [
            GPULeaseRequested(
                aggregate_id="lease-1",
                data={
                    "agent_id": "agent-1",
                    "hardware_id": "hw-1",
                    "gpu_model": "RTX 4090",
                    "gpu_count": 2,
                    "vram_gb": 24,
                    "duration_hours": 4,
                },
            ),
            GPULeaseProvisioned(
                aggregate_id="lease-1",
                data={
                    "deployment_id": "dep-1",
                    "total_cost_usdc": 50.0,
                    "ionet_fee_usdc": 5.0,
                },
            ),
            GPULeaseActivated(
                aggregate_id="lease-1",
                data={
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                },
            ),
        ]

        lease = GPULeaseAggregate.rebuild("lease-1", events)
        assert lease.lease_id == "lease-1"
        assert lease.agent_id == "agent-1"
        assert lease.hardware_id == "hw-1"
        assert lease.gpu_model == "RTX 4090"
        assert lease.gpu_count == 2
        assert lease.vram_gb == 24
        assert lease.duration_hours == 4
        assert lease.deployment_id == "dep-1"
        assert lease.total_cost_usdc == 50.0
        assert lease.ionet_fee_usdc == 5.0
        assert lease.status == LeaseStatus.ACTIVE
        assert lease.version == 3

    def test_rebuild_empty_events_returns_base(self):
        lease = GPULeaseAggregate.rebuild("lease-1", [])
        assert lease.lease_id == "lease-1"
        assert lease.status == LeaseStatus.REQUESTED
        assert lease.version == 0


class TestGPULeaseClearChanges:
    def test_clear_changes_empties_list(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        assert len(lease.get_changes()) == 1
        lease.clear_changes()
        assert len(lease.get_changes()) == 0

    def test_clear_changes_does_not_affect_state(self):
        lease = GPULeaseAggregate.request(
            lease_id="lease-1",
            agent_id="agent-1",
            hardware_id="hw-1",
            gpu_model="RTX 4090",
            gpu_count=1,
            vram_gb=24,
            duration_hours=2,
        )
        lease.clear_changes()
        assert lease.lease_id == "lease-1"
        assert lease.status == LeaseStatus.REQUESTED
