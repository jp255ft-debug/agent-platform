"""GPU leasing commands."""
from dataclasses import dataclass


@dataclass
class LeaseGPUCommand:
    """Command to request a GPU lease from io.net."""
    agent_id: str
    hardware_id: str
    duration_hours: int
    gpu_count: int = 1
    max_budget_usdc: float | None = None


@dataclass
class ExtendLeaseCommand:
    """Command to extend an active GPU lease."""
    lease_id: str
    additional_hours: int
    agent_id: str


@dataclass
class TerminateLeaseCommand:
    """Command to terminate a GPU lease early (kill-switch)."""
    lease_id: str
    agent_id: str
