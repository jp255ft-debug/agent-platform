"""GPU leasing command handlers."""
import uuid
from datetime import UTC, datetime
from typing import Optional

from app.application.commands.lease_gpu import (
    ExtendLeaseCommand,
    LeaseGPUCommand,
    TerminateLeaseCommand,
)
from app.domain.aggregates.gpu_lease import GPULeaseAggregate, LeaseStatus
from app.domain.repositories.event_store import EventStore
from app.infrastructure.depin.ionet_client import IonetClient
from app.infrastructure.depin.ionet_models import HardwareFilter


class GPUHandlers:
    """
    Handlers for GPU leasing commands.

    Orchestrates the interaction between:
    - io.net API (via IonetClient)
    - Event Store (via EventStore protocol)
    - GPULeaseAggregate (domain logic)
    """

    def __init__(
        self,
        event_store: EventStore,
        ionet_client: IonetClient,
    ):
        self._event_store = event_store
        self._ionet = ionet_client

    async def list_available_gpus(
        self,
        search: Optional[str] = None,
        min_vram: Optional[int] = None,
        max_price: Optional[float] = None,
    ) -> list[dict]:
        """List available GPUs with optional filters."""
        hw_filter = HardwareFilter(search=search, min_gpu_memory=min_vram)
        gpus = await self._ionet.list_gpus(hw_filter)

        # Apply additional client-side filters
        if max_price:
            gpus = [g for g in gpus if g.price <= max_price]

        return [
            {
                "id": g.id,
                "model": g.name,
                "gpu_count": g.num_cards,
                "vram_gb": g.vram_per_card,
                "total_vram_gb": g.total_vram_gb,
                "price_per_hour_usdc": g.price,
                "location": g.location,
                "is_available": g.is_available,
                "vcpu": g.vcpu,
                "memory_gb": g.memory,
                "storage_gb": g.storage,
            }
            for g in gpus
            if g.is_available
        ]

    async def request_lease(self, command: LeaseGPUCommand) -> dict:
        """Process a GPU lease request."""
        # 1. Calculate price on io.net
        price = await self._ionet.get_price(command.hardware_id, command.duration_hours)

        # 2. Check if agent has sufficient budget
        if command.max_budget_usdc and price.total_cost_usdc > command.max_budget_usdc:
            raise ValueError(
                f"Budget exceeded: {price.total_cost_usdc} USDC > "
                f"{command.max_budget_usdc} USDC"
            )

        # 3. Create lease aggregate
        lease_id = str(uuid.uuid4())
        # TODO: Fetch hardware specs from io.net to populate gpu_model and vram_gb
        lease = GPULeaseAggregate.request(
            lease_id=lease_id,
            agent_id=command.agent_id,
            hardware_id=command.hardware_id,
            gpu_model="",  # Will be populated from hardware lookup
            gpu_count=command.gpu_count,
            vram_gb=0,  # Will be populated from hardware lookup
            duration_hours=command.duration_hours,
        )

        # 4. Persist request event
        await self._event_store.append_events(
            lease_id, lease.get_changes(), expected_version=0,
        )
        lease.clear_changes()

        # 5. Provision on io.net
        deploy = await self._ionet.deploy_cluster(
            hardware_id=command.hardware_id,
            duration_hours=command.duration_hours,
            replica_count=command.gpu_count,
        )

        # 6. Update lease with deployment_id
        lease.provision(
            deployment_id=deploy.deployment_id,
            total_cost_usdc=price.total_cost_usdc,
            ionet_fee_usdc=price.ionet_fee,
        )

        # 7. Persist provision event
        await self._event_store.append_events(
            lease_id, lease.get_changes(), expected_version=1,
        )

        return {
            "lease_id": lease_id,
            "deployment_id": deploy.deployment_id,
            "status": "provisioning",
            "total_cost_usdc": price.total_cost_usdc,
            "ionet_fee_usdc": price.ionet_fee,
            "expires_at": lease.expires_at.isoformat() if lease.expires_at else None,
        }

    async def extend_lease(self, command: ExtendLeaseCommand) -> dict:
        """Extend an active lease."""
        # 1. Load lease from event store
        events = await self._event_store.load_stream(command.lease_id)
        if not events:
            raise ValueError(f"Lease {command.lease_id} not found")

        lease = GPULeaseAggregate.rebuild(command.lease_id, events)

        # 2. Verify ownership
        if lease.agent_id != command.agent_id:
            raise ValueError("Agent does not own this lease")

        # 3. Extend on io.net
        await self._ionet.extend_cluster(lease.deployment_id, command.additional_hours)

        # 4. Update aggregate
        lease.extend(command.additional_hours)

        # 5. Persist events
        await self._event_store.append_events(
            command.lease_id,
            lease.get_changes(),
            expected_version=lease.version,
        )

        return {
            "lease_id": command.lease_id,
            "new_expires_at": lease.expires_at.isoformat(),
            "new_duration_hours": lease.duration_hours,
        }

    async def terminate_lease(self, command: TerminateLeaseCommand) -> None:
        """Terminate a lease early (kill-switch)."""
        # 1. Load lease from event store
        events = await self._event_store.load_stream(command.lease_id)
        if not events:
            raise ValueError(f"Lease {command.lease_id} not found")

        lease = GPULeaseAggregate.rebuild(command.lease_id, events)

        # 2. Verify ownership
        if lease.agent_id != command.agent_id:
            raise ValueError("Agent does not own this lease")

        # 3. Destroy cluster on io.net
        if lease.deployment_id:
            await self._ionet.destroy_cluster(lease.deployment_id)

        # 4. Update aggregate
        lease.terminate(reason="kill_switch")

        # 5. Persist events
        await self._event_store.append_events(
            command.lease_id,
            lease.get_changes(),
            expected_version=lease.version,
        )

    async def get_lease(self, lease_id: str, agent_id: str) -> dict:
        """Get lease status."""
        events = await self._event_store.load_stream(lease_id)
        if not events:
            raise ValueError(f"Lease {lease_id} not found")

        lease = GPULeaseAggregate.rebuild(lease_id, events)

        if lease.agent_id != agent_id:
            raise ValueError("Agent does not own this lease")

        # Calculate remaining hours
        remaining_hours = None
        is_active = lease.status in (LeaseStatus.ACTIVE, LeaseStatus.EXTENDING)
        if is_active and lease.expires_at:
            now = datetime.now(UTC)
            remaining = (lease.expires_at - now).total_seconds() / 3600
            remaining_hours = max(0.0, round(remaining, 2))

        return {
            "lease_id": lease.lease_id,
            "status": lease.status,
            "gpu_model": lease.gpu_model,
            "gpu_count": lease.gpu_count,
            "duration_hours": lease.duration_hours,
            "deployment_id": lease.deployment_id,
            "total_cost_usdc": lease.total_cost_usdc,
            "ionet_fee_usdc": lease.ionet_fee_usdc,
            "remaining_hours": remaining_hours,
            "is_active": is_active,
            "created_at": lease.created_at.isoformat() if lease.created_at else None,
            "activated_at": lease.activated_at.isoformat() if lease.activated_at else None,
            "expires_at": lease.expires_at.isoformat() if lease.expires_at else None,
        }
