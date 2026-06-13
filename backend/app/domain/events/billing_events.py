from app.domain.events.base import DomainEvent

class BillingSessionStarted(DomainEvent):
    def __init__(self, session_id: str, agent_id: str, resource_type: str):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "agent_id": agent_id,
            "resource_type": resource_type})

class ResourceConsumed(DomainEvent):
    def __init__(self, session_id: str, agent_id: str, amount: int, resource_type: str):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "agent_id": agent_id,
            "amount": amount, "resource_type": resource_type})

class BillingSessionClosed(DomainEvent):
    def __init__(self, session_id: str, total_consumed: int):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "total_consumed": total_consumed})

class BillingSessionSettled(DomainEvent):
    def __init__(self, session_id: str, tx_hash: str, amount_paid: int):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "tx_hash": tx_hash, "amount_paid": amount_paid})
