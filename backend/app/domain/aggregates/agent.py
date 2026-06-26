
from app.domain.events.agent_events import (
    AgentDelegated,
    AgentDelegationRevoked,
    AgentRegistered,
    AgentReputationUpdated,
)
from app.domain.events.base import DomainEvent


class AgentAggregate:
    def __init__(self, agent_id: str):
        self.agent_id: str = agent_id
        self.owner_address: str | None = None
        self.delegation_address: str | None = None
        self.delegation_active: bool = False
        self.reputation_score: int = 100
        self.version: int = 0
        self._changes: list[DomainEvent] = []

    @staticmethod
    def register(agent_id: str, owner_address: str, delegation_address: str | None = None):
        agent = AgentAggregate(agent_id)
        event = AgentRegistered(agent_id, owner_address, delegation_address)
        agent._apply(event)
        agent._changes.append(event)
        return agent

    def delegate(self, delegate_address: str, expires_at: str) -> None:
        event = AgentDelegated(self.agent_id, delegate_address, expires_at)
        self._apply(event)
        self._changes.append(event)

    def revoke_delegation(self) -> None:
        event = AgentDelegationRevoked(self.agent_id)
        self._apply(event)
        self._changes.append(event)

    def update_reputation(self, new_score: int, reason: str) -> None:
        event = AgentReputationUpdated(self.agent_id, new_score, reason)
        self._apply(event)
        self._changes.append(event)

    def _apply(self, event: DomainEvent) -> None:
        if isinstance(event, AgentRegistered):
            self.owner_address = event.data["owner_address"]
            self.delegation_address = event.data.get("delegation_address")
        elif isinstance(event, AgentDelegated):
            self.delegation_address = event.data["delegate_address"]
            self.delegation_active = True
        elif isinstance(event, AgentDelegationRevoked):
            self.delegation_active = False
        elif isinstance(event, AgentReputationUpdated):
            self.reputation_score = event.data["new_score"]
        self.version += 1

    def get_changes(self) -> list[DomainEvent]:
        return self._changes.copy()

    def clear_changes(self) -> None:
        self._changes.clear()
