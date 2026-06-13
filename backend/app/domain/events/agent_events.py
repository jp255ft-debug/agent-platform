from app.domain.events.base import DomainEvent

class AgentRegistered(DomainEvent):
    def __init__(self, agent_id: str, owner_address: str, delegation_address: str | None = None):
        super().__init__(aggregate_id=agent_id, data={
            "agent_id": agent_id, "owner_address": owner_address,
            "delegation_address": delegation_address})

class AgentDelegated(DomainEvent):
    def __init__(self, agent_id: str, delegate_address: str, expires_at: str):
        super().__init__(aggregate_id=agent_id, data={
            "agent_id": agent_id, "delegate_address": delegate_address,
            "expires_at": expires_at})

class AgentDelegationRevoked(DomainEvent):
    def __init__(self, agent_id: str):
        super().__init__(aggregate_id=agent_id, data={"agent_id": agent_id})

class AgentReputationUpdated(DomainEvent):
    def __init__(self, agent_id: str, new_score: int, reason: str):
        super().__init__(aggregate_id=agent_id, data={
            "agent_id": agent_id, "new_score": new_score, "reason": reason})
