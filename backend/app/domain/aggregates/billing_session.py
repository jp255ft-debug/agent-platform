from typing import List
from app.domain.events.base import DomainEvent
from app.domain.events.billing_events import (
    BillingSessionStarted, ResourceConsumed, BillingSessionClosed, BillingSessionSettled)

class BillingSessionAggregate:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.agent_id: str | None = None
        self.resource_type: str | None = None
        self.total_consumed: int = 0
        self.status: str = "pending"
        self.version: int = 0
        self._changes: List[DomainEvent] = []

    @staticmethod
    def start(session_id: str, agent_id: str, resource_type: str):
        session = BillingSessionAggregate(session_id)
        event = BillingSessionStarted(session_id, agent_id, resource_type)
        session._apply(event)
        session._changes.append(event)
        return session

    def record_consumption(self, amount: int) -> None:
        event = ResourceConsumed(self.session_id, self.agent_id, amount, self.resource_type)
        self._apply(event)
        self._changes.append(event)

    def close(self) -> None:
        event = BillingSessionClosed(self.session_id, self.total_consumed)
        self._apply(event)
        self._changes.append(event)

    def settle(self, tx_hash: str, amount_paid: int) -> None:
        event = BillingSessionSettled(self.session_id, tx_hash, amount_paid)
        self._apply(event)
        self._changes.append(event)

    def _apply(self, event: DomainEvent) -> None:
        if isinstance(event, BillingSessionStarted):
            self.agent_id = event.data["agent_id"]
            self.resource_type = event.data["resource_type"]
            self.status = "active"
        elif isinstance(event, ResourceConsumed):
            self.total_consumed += event.data["amount"]
        elif isinstance(event, BillingSessionClosed):
            self.status = "closed"
        elif isinstance(event, BillingSessionSettled):
            self.status = "settled"
        self.version += 1

    def get_changes(self) -> List[DomainEvent]:
        return self._changes.copy()

    def clear_changes(self) -> None:
        self._changes.clear()
