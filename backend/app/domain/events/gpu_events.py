"""GPU leasing domain events."""
from app.domain.events.base import DomainEvent


class GPULeaseRequested(DomainEvent):
    """Emitted when a GPU lease is requested by an agent."""

    def __init__(
        self,
        aggregate_id: str,
        data: dict | None = None,
    ):
        super().__init__(aggregate_id=aggregate_id, data=data)


class GPULeaseProvisioned(DomainEvent):
    """Emitted when the io.net deployment has been created."""

    def __init__(
        self,
        aggregate_id: str,
        data: dict | None = None,
    ):
        super().__init__(aggregate_id=aggregate_id, data=data)


class GPULeaseActivated(DomainEvent):
    """Emitted when the lease becomes active (deployment confirmed)."""

    def __init__(
        self,
        aggregate_id: str,
        data: dict | None = None,
    ):
        super().__init__(aggregate_id=aggregate_id, data=data)


class GPULeaseExtended(DomainEvent):
    """Emitted when the lease duration is extended."""

    def __init__(
        self,
        aggregate_id: str,
        data: dict | None = None,
    ):
        super().__init__(aggregate_id=aggregate_id, data=data)


class GPULeaseTerminated(DomainEvent):
    """Emitted when the lease is terminated early (kill-switch)."""

    def __init__(
        self,
        aggregate_id: str,
        data: dict | None = None,
    ):
        super().__init__(aggregate_id=aggregate_id, data=data)


class GPULeaseExpired(DomainEvent):
    """Emitted when the lease expires naturally."""

    def __init__(
        self,
        aggregate_id: str,
        data: dict | None = None,
    ):
        super().__init__(aggregate_id=aggregate_id, data=data)
