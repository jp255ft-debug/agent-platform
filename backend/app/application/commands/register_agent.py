"""Agent registration and management commands."""
from dataclasses import dataclass


@dataclass
class RegisterAgentCommand:
    agent_id: str
    owner_address: str
    delegation_address: str | None = None


@dataclass
class DelegateAgentCommand:
    agent_id: str
    delegate_address: str
    expires_at: str


@dataclass
class RevokeDelegationCommand:
    agent_id: str


@dataclass
class UpdateReputationCommand:
    agent_id: str
    new_score: int
    reason: str
