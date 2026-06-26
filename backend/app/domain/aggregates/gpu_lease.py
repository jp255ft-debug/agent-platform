"""GPU Lease aggregate — manages GPU leasing lifecycle via io.net."""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.domain.events.base import DomainEvent
from app.domain.events.gpu_events import (
    GPULeaseActivated,
    GPULeaseExpired,
    GPULeaseExtended,
    GPULeaseProvisioned,
    GPULeaseRequested,
    GPULeaseTerminated,
)


class LeaseStatus:
    """Possible statuses for a GPU lease (string-based, matching existing patterns)."""
    REQUESTED = "requested"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    EXTENDING = "extending"
    TERMINATED = "terminated"
    EXPIRED = "expired"


@dataclass
class GPULeaseAggregate:
    """
    Aggregate for managing GPU leasing via io.net.

    Follows the same Event Sourcing pattern as AgentAggregate:
    - State mutations happen through _apply(event)
    - Changes are tracked via _changes list
    - Optimistic concurrency via version counter
    """

    lease_id: str
    agent_id: str = ""
    hardware_id: str = ""
    gpu_model: str = ""
    gpu_count: int = 0
    vram_gb: int = 0
    duration_hours: int = 0
    deployment_id: Optional[str] = None
    status: str = LeaseStatus.REQUESTED
    total_cost_usdc: float = 0.0
    ionet_fee_usdc: float = 0.0
    created_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    version: int = 0
    _changes: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def request(
        lease_id: str,
        agent_id: str,
        hardware_id: str,
        gpu_model: str,
        gpu_count: int,
        vram_gb: int,
        duration_hours: int,
    ) -> "GPULeaseAggregate":
        """Create a new GPU lease aggregate in REQUESTED status."""
        now = datetime.now(UTC)
        lease = GPULeaseAggregate(
            lease_id=lease_id,
            agent_id=agent_id,
            hardware_id=hardware_id,
            gpu_model=gpu_model,
            gpu_count=gpu_count,
            vram_gb=vram_gb,
            duration_hours=duration_hours,
            status=LeaseStatus.REQUESTED,
            created_at=now,
        )
        event = GPULeaseRequested(
            aggregate_id=lease_id,
            data={
                "agent_id": agent_id,
                "hardware_id": hardware_id,
                "gpu_model": gpu_model,
                "gpu_count": gpu_count,
                "vram_gb": vram_gb,
                "duration_hours": duration_hours,
                "created_at": now.isoformat(),
            },
        )
        lease._apply(event)
        lease._changes.append(event)
        return lease

    @staticmethod
    def rebuild(lease_id: str, events: list[DomainEvent]) -> "GPULeaseAggregate":
        """Rebuild aggregate state from event history."""
        lease = GPULeaseAggregate(lease_id=lease_id)
        for event in events:
            lease._apply(event)
        return lease

    def provision(self, deployment_id: str, total_cost_usdc: float, ionet_fee_usdc: float):
        """Update with io.net deployment provisioning data."""
        if self.status != LeaseStatus.REQUESTED:
            raise ValueError(f"Cannot provision lease in status {self.status}")

        self.deployment_id = deployment_id
        self.total_cost_usdc = total_cost_usdc
        self.ionet_fee_usdc = ionet_fee_usdc
        self.status = LeaseStatus.PROVISIONING

        event = GPULeaseProvisioned(
            aggregate_id=self.lease_id,
            data={
                "deployment_id": deployment_id,
                "total_cost_usdc": total_cost_usdc,
                "ionet_fee_usdc": ionet_fee_usdc,
            },
        )
        self._apply(event)
        self._changes.append(event)

    def activate(self):
        """Activate the lease after io.net deployment confirmation."""
        if self.status != LeaseStatus.PROVISIONING:
            raise ValueError(f"Cannot activate lease in status {self.status}")

        self.status = LeaseStatus.ACTIVE
        self.activated_at = datetime.now(UTC)
        self.expires_at = self.activated_at + timedelta(hours=self.duration_hours)

        event = GPULeaseActivated(
            aggregate_id=self.lease_id,
            data={
                "activated_at": self.activated_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
            },
        )
        self._apply(event)
        self._changes.append(event)

    def extend(self, additional_hours: int):
        """Extend the lease duration."""
        if self.status not in [LeaseStatus.ACTIVE, LeaseStatus.EXTENDING]:
            raise ValueError(f"Cannot extend lease in status {self.status}")

        self.duration_hours += additional_hours
        self.expires_at = (self.expires_at or datetime.now(UTC)) + timedelta(hours=additional_hours)
        self.status = LeaseStatus.EXTENDING

        event = GPULeaseExtended(
            aggregate_id=self.lease_id,
            data={
                "additional_hours": additional_hours,
                "new_duration_hours": self.duration_hours,
                "new_expires_at": self.expires_at.isoformat(),
            },
        )
        self._apply(event)
        self._changes.append(event)

    def terminate(self, reason: str = "manual"):
        """Terminate the lease early (kill-switch)."""
        if self.status in [LeaseStatus.TERMINATED, LeaseStatus.EXPIRED]:
            return

        self.status = LeaseStatus.TERMINATED
        self.terminated_at = datetime.now(UTC)

        event = GPULeaseTerminated(
            aggregate_id=self.lease_id,
            data={"reason": reason, "terminated_at": self.terminated_at.isoformat()},
        )
        self._apply(event)
        self._changes.append(event)

    def expire(self):
        """Mark the lease as expired (when time runs out)."""
        if self.status != LeaseStatus.ACTIVE:
            return

        self.status = LeaseStatus.EXPIRED

        event = GPULeaseExpired(
            aggregate_id=self.lease_id,
            data={"expired_at": datetime.now(UTC).isoformat()},
        )
        self._apply(event)
        self._changes.append(event)

    def _apply(self, event: DomainEvent):
        """Apply an event to mutate aggregate state."""
        if isinstance(event, GPULeaseRequested):
            self.agent_id = event.data.get("agent_id", "")
            self.hardware_id = event.data.get("hardware_id", "")
            self.gpu_model = event.data.get("gpu_model", "")
            self.gpu_count = event.data.get("gpu_count", 0)
            self.vram_gb = event.data.get("vram_gb", 0)
            self.duration_hours = event.data.get("duration_hours", 0)
            created = event.data.get("created_at")
            if created:
                self.created_at = datetime.fromisoformat(created)
        elif isinstance(event, GPULeaseProvisioned):
            self.deployment_id = event.data.get("deployment_id")
            self.total_cost_usdc = event.data.get("total_cost_usdc", 0.0)
            self.ionet_fee_usdc = event.data.get("ionet_fee_usdc", 0.0)
            self.status = LeaseStatus.PROVISIONING
        elif isinstance(event, GPULeaseActivated):
            self.status = LeaseStatus.ACTIVE
            activated = event.data.get("activated_at")
            expires = event.data.get("expires_at")
            if activated:
                self.activated_at = datetime.fromisoformat(activated)
            if expires:
                self.expires_at = datetime.fromisoformat(expires)
        elif isinstance(event, GPULeaseExtended):
            self.duration_hours = event.data.get("new_duration_hours", self.duration_hours)
            expires = event.data.get("new_expires_at")
            if expires:
                self.expires_at = datetime.fromisoformat(expires)
            self.status = LeaseStatus.EXTENDING
        elif isinstance(event, GPULeaseTerminated):
            self.status = LeaseStatus.TERMINATED
            terminated = event.data.get("terminated_at")
            if terminated:
                self.terminated_at = datetime.fromisoformat(terminated)
        elif isinstance(event, GPULeaseExpired):
            self.status = LeaseStatus.EXPIRED
        self.version += 1

    def get_changes(self) -> list[DomainEvent]:
        """Return pending changes and clear the list."""
        return self._changes.copy()

    def clear_changes(self) -> None:
        """Clear pending changes after persistence."""
        self._changes.clear()
