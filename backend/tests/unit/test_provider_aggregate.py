"""Unit tests for ProviderAggregate (DePIN GPU Provider)."""
import pytest
from datetime import datetime, timezone

from app.domain.aggregates.provider import (
    ProviderAggregate,
    ProviderStatus,
    GPUSpecs,
    MIN_STAKE_REQUIRED,
)
from app.domain.events.provider_events import (
    ProviderRegistered,
    ProviderStatusChanged,
    HealthReported,
    SlashingApplied,
    ProviderStaked,
    ProviderUnstaked,
    GPUSpecsUpdated,
    ProviderJobCompleted,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gpu_specs():
    return GPUSpecs(
        model="NVIDIA H100",
        vram_gb=80,
        tflops_fp16=151.0,
        tflops_fp32=75.0,
        cuda_cores=18432,
        memory_bandwidth_gbps=3350.0,
        driver_version="550.54.15",
        price_per_tflops_hour=0.05,
    )


@pytest.fixture
def registered_provider(gpu_specs):
    """Creates a provider that has been registered (PENDING status)."""
    provider = ProviderAggregate.register(
        provider_id="provider-1",
        owner_address="0x1234567890abcdef",
        gpu_specs=gpu_specs,
    )
    provider.clear_changes()
    return provider


@pytest.fixture
def active_provider(registered_provider):
    """Creates a provider that is ACTIVE with sufficient stake."""
    registered_provider.stake(MIN_STAKE_REQUIRED)
    registered_provider.clear_changes()
    registered_provider.activate()
    registered_provider.clear_changes()
    return registered_provider


# ---------------------------------------------------------------------------
# GPUSpecs
# ---------------------------------------------------------------------------

class TestGPUSpecs:
    def test_to_dict_roundtrip(self):
        specs = GPUSpecs(
            model="NVIDIA H100",
            vram_gb=80,
            tflops_fp16=151.0,
            tflops_fp32=75.0,
            cuda_cores=18432,
            memory_bandwidth_gbps=3350.0,
            driver_version="550.54.15",
            price_per_tflops_hour=0.05,
        )
        d = specs.to_dict()
        restored = GPUSpecs.from_dict(d)
        assert restored.model == specs.model
        assert restored.vram_gb == specs.vram_gb
        assert restored.tflops_fp16 == specs.tflops_fp16

    def test_from_dict_with_defaults(self):
        restored = GPUSpecs.from_dict({})
        assert restored.model == "unknown"
        assert restored.vram_gb == 0
        assert restored.tflops_fp16 == 0.0


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

class TestProviderRegister:
    def test_register_creates_provider_in_pending_status(self, gpu_specs):
        provider = ProviderAggregate.register(
            provider_id="provider-1",
            owner_address="0x1234567890abcdef",
            gpu_specs=gpu_specs,
        )
        assert provider.provider_id == "provider-1"
        assert provider.owner_address == "0x1234567890abcdef"
        assert provider.gpu_specs == gpu_specs
        assert provider.status == ProviderStatus.PENDING
        assert provider.reputation_score == 100
        assert provider.staked_amount == 0
        assert provider.registered_at is not None

    def test_register_emits_provider_registered_event(self, gpu_specs):
        provider = ProviderAggregate.register(
            provider_id="provider-1",
            owner_address="0x1234567890abcdef",
            gpu_specs=gpu_specs,
        )
        changes = provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], ProviderRegistered)
        assert changes[0].data["owner_address"] == "0x1234567890abcdef"

    def test_register_sets_registered_at(self, gpu_specs):
        provider = ProviderAggregate.register(
            provider_id="provider-1",
            owner_address="0x1234567890abcdef",
            gpu_specs=gpu_specs,
        )
        assert provider.registered_at is not None
        assert isinstance(provider.registered_at, datetime)


# ---------------------------------------------------------------------------
# Activate
# ---------------------------------------------------------------------------

class TestProviderActivate:
    def test_activate_success(self, registered_provider):
        registered_provider.stake(MIN_STAKE_REQUIRED)
        registered_provider.clear_changes()
        registered_provider.activate()
        assert registered_provider.status == ProviderStatus.ACTIVE
        changes = registered_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], ProviderStatusChanged)
        assert changes[0].data["new_status"] == "active"

    def test_activate_fails_when_not_pending(self, active_provider):
        with pytest.raises(ValueError, match="Cannot activate"):
            active_provider.activate()

    def test_activate_fails_when_stake_below_minimum(self, registered_provider):
        with pytest.raises(ValueError, match="below minimum"):
            registered_provider.activate()


# ---------------------------------------------------------------------------
# Suspend
# ---------------------------------------------------------------------------

class TestProviderSuspend:
    def test_suspend_success(self, active_provider):
        active_provider.suspend(reason="maintenance")
        assert active_provider.status == ProviderStatus.SUSPENDED
        changes = active_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], ProviderStatusChanged)
        assert changes[0].data["new_status"] == "suspended"

    def test_suspend_fails_when_not_active(self, registered_provider):
        with pytest.raises(ValueError, match="Cannot suspend"):
            registered_provider.suspend()


# ---------------------------------------------------------------------------
# Mark Inactive
# ---------------------------------------------------------------------------

class TestProviderMarkInactive:
    def test_mark_inactive_from_active(self, active_provider):
        active_provider.mark_inactive()
        assert active_provider.status == ProviderStatus.INACTIVE

    def test_mark_inactive_from_suspended(self, active_provider):
        active_provider.suspend()
        active_provider.clear_changes()
        active_provider.mark_inactive()
        assert active_provider.status == ProviderStatus.INACTIVE

    def test_mark_inactive_fails_from_pending(self, registered_provider):
        with pytest.raises(ValueError, match="Cannot mark inactive"):
            registered_provider.mark_inactive()


# ---------------------------------------------------------------------------
# Health Report
# ---------------------------------------------------------------------------

class TestReportHealth:
    def test_report_health_online(self, active_provider):
        active_provider.report_health(uptime_seconds=3600, is_online=True)
        assert active_provider.total_uptime_seconds == 3600
        assert active_provider.last_health_report is not None
        changes = active_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], HealthReported)
        assert changes[0].data["is_online"] is True

    def test_report_health_offline_does_not_add_uptime(self, active_provider):
        active_provider.report_health(uptime_seconds=3600, is_online=False)
        assert active_provider.total_uptime_seconds == 0

    def test_report_health_ignored_when_slashed(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=100, reason="fraud")
        active_provider.clear_changes()
        active_provider.report_health(uptime_seconds=3600, is_online=True)
        assert active_provider.total_uptime_seconds == 0

    def test_report_health_with_gpu_stats(self, active_provider):
        gpu_stats = {"utilization_pct": 85.0, "temperature_c": 72.0, "memory_used_gb": 40.0}
        active_provider.report_health(uptime_seconds=3600, is_online=True, gpu_stats=gpu_stats)
        changes = active_provider.get_changes()
        assert changes[0].data["gpu_stats"] == gpu_stats


# ---------------------------------------------------------------------------
# Slashing
# ---------------------------------------------------------------------------

class TestApplySlashing:
    def test_slashing_reduces_stake_and_reputation(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=50, reason="compute_fraud")
        # active_provider already had MIN_STAKE_REQUIRED from fixture, then staked another MIN_STAKE_REQUIRED
        # total = 2 * MIN_STAKE_REQUIRED, slashing 50% = MIN_STAKE_REQUIRED
        assert active_provider.staked_amount == MIN_STAKE_REQUIRED
        assert active_provider.reputation_score == 50

    def test_slashing_below_threshold_sets_slashed_status(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=100, reason="severe_fraud")
        assert active_provider.status == ProviderStatus.SLASHED

    def test_slashing_already_slashed_is_noop(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=100, reason="fraud")
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=50, reason="again")
        # Should be noop - no new changes
        assert len(active_provider.get_changes()) == 0

    def test_slashing_invalid_percent_raises_error(self, active_provider):
        with pytest.raises(ValueError, match="Penalty percent"):
            active_provider.apply_slashing(penalty_percent=150, reason="invalid")

    def test_slashing_emits_slashing_applied_event(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=30, reason="downtime")
        changes = active_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], SlashingApplied)
        assert changes[0].data["penalty_percent"] == 30
        assert changes[0].data["reason"] == "downtime"


# ---------------------------------------------------------------------------
# Staking
# ---------------------------------------------------------------------------

class TestStaking:
    def test_stake_increases_staked_amount(self, registered_provider):
        registered_provider.stake(5_000_000)
        assert registered_provider.staked_amount == 5_000_000
        changes = registered_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], ProviderStaked)

    def test_stake_positive_amount_required(self, registered_provider):
        with pytest.raises(ValueError, match="positive"):
            registered_provider.stake(0)

    def test_unstake_reduces_staked_amount(self, registered_provider):
        registered_provider.stake(MIN_STAKE_REQUIRED + 1_000_000)
        registered_provider.clear_changes()
        registered_provider.unstake(1_000_000)
        assert registered_provider.staked_amount == MIN_STAKE_REQUIRED
        changes = registered_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], ProviderUnstaked)

    def test_unstake_below_minimum_raises_error(self, registered_provider):
        registered_provider.stake(MIN_STAKE_REQUIRED)
        with pytest.raises(ValueError, match="below minimum"):
            registered_provider.unstake(1)

    def test_unstake_more_than_staked_raises_error(self, registered_provider):
        registered_provider.stake(5_000_000)
        with pytest.raises(ValueError, match="Insufficient"):
            registered_provider.unstake(10_000_000)

    def test_unstake_positive_amount_required(self, registered_provider):
        with pytest.raises(ValueError, match="positive"):
            registered_provider.unstake(0)


# ---------------------------------------------------------------------------
# GPU Specs Update
# ---------------------------------------------------------------------------

class TestUpdateGPUSpecs:
    def test_update_gpu_specs_success(self, registered_provider):
        new_specs = GPUSpecs(
            model="NVIDIA A100",
            vram_gb=40,
            tflops_fp16=78.0,
            tflops_fp32=39.0,
            cuda_cores=6912,
            memory_bandwidth_gbps=1555.0,
            driver_version="550.54.15",
            price_per_tflops_hour=0.03,
        )
        registered_provider.update_gpu_specs(new_specs)
        assert registered_provider.gpu_specs.model == "NVIDIA A100"
        changes = registered_provider.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], GPUSpecsUpdated)

    def test_update_gpu_specs_fails_when_slashed(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=100, reason="fraud")
        new_specs = GPUSpecs(
            model="NVIDIA A100",
            vram_gb=40,
            tflops_fp16=78.0,
            tflops_fp32=39.0,
            cuda_cores=6912,
            memory_bandwidth_gbps=1555.0,
            driver_version="550.54.15",
            price_per_tflops_hour=0.03,
        )
        with pytest.raises(ValueError, match="Cannot update specs"):
            active_provider.update_gpu_specs(new_specs)


# ---------------------------------------------------------------------------
# Job Completion
# ---------------------------------------------------------------------------

class TestRecordJobCompletion:
    def test_successful_job_increases_reputation(self, registered_provider):
        registered_provider.record_job_completion(
            session_id="session-1",
            agent_id="agent-1",
            success=True,
            compute_time_seconds=3600,
        )
        assert registered_provider.reputation_score == 100  # capped at 100
        assert registered_provider.total_jobs_completed == 1

    def test_failed_job_decreases_reputation(self, registered_provider):
        registered_provider.record_job_completion(
            session_id="session-1",
            agent_id="agent-1",
            success=False,
            compute_time_seconds=3600,
        )
        assert registered_provider.reputation_score == 98
        assert registered_provider.total_jobs_failed == 1

    def test_reputation_capped_at_100(self, registered_provider):
        for _ in range(5):
            registered_provider.record_job_completion(
                session_id="s1", agent_id="a1", success=True, compute_time_seconds=3600,
            )
        assert registered_provider.reputation_score == 100

    def test_reputation_floor_at_0(self, registered_provider):
        for _ in range(60):
            registered_provider.record_job_completion(
                session_id="s1", agent_id="a1", success=False, compute_time_seconds=3600,
            )
        assert registered_provider.reputation_score == 0

    def test_job_with_proof_hash(self, registered_provider):
        registered_provider.record_job_completion(
            session_id="session-1",
            agent_id="agent-1",
            success=True,
            compute_time_seconds=3600,
            proof_hash="0xabc123",
        )
        changes = registered_provider.get_changes()
        assert changes[0].data["proof_hash"] == "0xabc123"


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestProviderProperties:
    def test_is_active_true_when_active(self, active_provider):
        assert active_provider.is_active is True

    def test_is_active_false_when_pending(self, registered_provider):
        assert registered_provider.is_active is False

    def test_is_active_false_when_slashed(self, active_provider):
        active_provider.stake(MIN_STAKE_REQUIRED)
        active_provider.clear_changes()
        active_provider.apply_slashing(penalty_percent=100, reason="fraud")
        assert active_provider.is_active is False

    def test_uptime_percentage_no_jobs(self, registered_provider):
        assert registered_provider.uptime_percentage == 0.0

    def test_uptime_percentage_all_success(self, registered_provider):
        registered_provider.record_job_completion(
            session_id="s1", agent_id="a1", success=True, compute_time_seconds=3600,
        )
        registered_provider.record_job_completion(
            session_id="s2", agent_id="a1", success=True, compute_time_seconds=1800,
        )
        assert registered_provider.uptime_percentage == 100.0

    def test_uptime_percentage_mixed(self, registered_provider):
        registered_provider.record_job_completion(
            session_id="s1", agent_id="a1", success=True, compute_time_seconds=3600,
        )
        registered_provider.record_job_completion(
            session_id="s2", agent_id="a1", success=False, compute_time_seconds=1800,
        )
        assert registered_provider.uptime_percentage == 50.0

    def test_can_be_activated_true_with_sufficient_stake(self, registered_provider):
        registered_provider.stake(MIN_STAKE_REQUIRED)
        assert registered_provider.can_be_activated is True

    def test_can_be_activated_false_with_insufficient_stake(self, registered_provider):
        assert registered_provider.can_be_activated is False


# ---------------------------------------------------------------------------
# Event Sourcing
# ---------------------------------------------------------------------------

class TestProviderEventSourcing:
    def test_rebuild_from_events(self, gpu_specs):
        provider = ProviderAggregate(
            provider_id="provider-1",
            owner_address="0x1234567890abcdef",
        )
        event1 = ProviderRegistered(
            aggregate_id="provider-1",
            data={
                "owner_address": "0x1234567890abcdef",
                "gpu_specs": gpu_specs.to_dict(),
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        event2 = ProviderStaked(
            aggregate_id="provider-1",
            data={"amount": MIN_STAKE_REQUIRED, "total_staked": MIN_STAKE_REQUIRED},
        )
        event3 = ProviderStatusChanged(
            aggregate_id="provider-1",
            data={
                "old_status": "pending",
                "new_status": "active",
                "reason": "activation",
            }
        )
        provider._apply(event1)
        provider._apply(event2)
        provider._apply(event3)
        assert provider.owner_address == "0x1234567890abcdef"
        assert provider.gpu_specs.model == gpu_specs.model
        assert provider.staked_amount == MIN_STAKE_REQUIRED
        assert provider.status == ProviderStatus.ACTIVE
        assert provider.version == 3

    def test_get_changes_returns_copy(self, gpu_specs):
        provider = ProviderAggregate.register(
            provider_id="p1", owner_address="0x1234", gpu_specs=gpu_specs,
        )
        changes = provider.get_changes()
        assert len(changes) == 1
        changes.clear()
        assert len(provider.get_changes()) == 1

    def test_clear_changes_empties_list(self, gpu_specs):
        provider = ProviderAggregate.register(
            provider_id="p1", owner_address="0x1234", gpu_specs=gpu_specs,
        )
        provider.clear_changes()
        assert len(provider.get_changes()) == 0

    def test_version_increments_on_each_event(self, gpu_specs):
        provider = ProviderAggregate.register(
            provider_id="p1", owner_address="0x1234", gpu_specs=gpu_specs,
        )
        assert provider.version == 1
        provider.stake(5_000_000)
        assert provider.version == 2
