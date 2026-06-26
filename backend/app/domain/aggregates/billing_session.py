
from app.domain.events.base import DomainEvent
from app.domain.events.billing_events import (
    BillingSessionClosed,
    BillingSessionSettled,
    BillingSessionStarted,
    ResourceConsumed,
    ResourceConsumedV2,
)


class BillingSessionAggregate:
    """Agregado de sessão de billing com suporte a DePIN Procurement.

    Agora emite ResourceConsumedV2 em vez de ResourceConsumed para novos registros.
    O ResourceConsumed (V1) legado ainda é aceito no _apply para reconstrução
    de eventos históricos via EventUpcaster.
    """
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.agent_id: str | None = None
        self.resource_type: str | None = None
        self.provider_id: str | None = None
        self.total_consumed: int = 0
        self.total_cost_micro_usdc: int = 0
        self.status: str = "pending"
        self.version: int = 0
        self._changes: list[DomainEvent] = []

    @staticmethod
    def start(session_id: str, agent_id: str, resource_type: str,
              provider_id: str | None = None):
        session = BillingSessionAggregate(session_id)
        session.provider_id = provider_id
        event = BillingSessionStarted(session_id, agent_id, resource_type)
        session._apply(event)
        session._changes.append(event)
        return session

    def record_consumption(self, amount: int,
                           cost_micro_usdc: int = 0,
                           provider_id: str | None = None) -> None:
        """Registra consumo de recurso com semântica DePIN.

        Args:
            amount: Quantidade de recurso consumido (ex: TFLOPS)
            cost_micro_usdc: Custo em micro USDC (1 USDC = 1_000_000 micro_usdc)
            provider_id: ID do provedor DePIN que forneceu o recurso
        """
        event = ResourceConsumedV2(
            aggregate_id=self.session_id,
            session_id=self.session_id,
            agent_id=self.agent_id or "",
            resource_type=self.resource_type or "unknown",
            amount=amount,
            cost_micro_usdc=cost_micro_usdc,
            provider_id=provider_id or self.provider_id or "legacy_system",
        )
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
            # V1 legado — aceito para reconstrução de eventos históricos
            self.total_consumed += event.data["amount"]
        elif isinstance(event, ResourceConsumedV2):
            # V2 — novo formato com custo e provedor
            self.total_consumed += event.data["amount"]
            self.total_cost_micro_usdc += event.data.get("cost_micro_usdc", 0)
            self.provider_id = event.data.get("provider_id", self.provider_id)
        elif isinstance(event, BillingSessionClosed):
            self.status = "closed"
        elif isinstance(event, BillingSessionSettled):
            self.status = "settled"
        self.version += 1

    def get_changes(self) -> list[DomainEvent]:
        return self._changes.copy()

    def clear_changes(self) -> None:
        self._changes.clear()


