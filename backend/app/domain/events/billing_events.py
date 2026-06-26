from app.domain.events.base import DomainEvent


class BillingSessionStarted(DomainEvent):
    def __init__(self, session_id: str, agent_id: str, resource_type: str):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "agent_id": agent_id,
            "resource_type": resource_type})

class ResourceConsumed(DomainEvent):
    """V1: Legacy resource consumption event (pre-DePIN migration).

    Mantido para referência histórica. Novos comandos devem usar
    ResourceConsumedV2. O EventUpcaster transforma V1 em V2 na leitura.
    """
    def __init__(self, session_id: str, agent_id: str, amount: int, resource_type: str):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "agent_id": agent_id,
            "amount": amount, "resource_type": resource_type})

class ResourceConsumedV2(DomainEvent):
    """V2: Resource consumption with DePIN Procurement semantics.

    Adiciona campos para governança de custo em provedores DePIN:
    - cost_micro_usdc: Custo em micro USDC (1 USDC = 1_000_000 micro_usdc)
      Uso de inteiros previne erros de arredondamento de ponto flutuante.
    - provider_id: Identificador do nó/provedor DePIN que forneceu o recurso.
    """
    def __init__(self, aggregate_id: str, session_id: str, agent_id: str,
                 resource_type: str, amount: int,
                 cost_micro_usdc: int = 0,
                 provider_id: str = "legacy_system"):
        super().__init__(aggregate_id=aggregate_id, data={
            "session_id": session_id,
            "agent_id": agent_id,
            "resource_type": resource_type,
            "amount": amount,
            "cost_micro_usdc": cost_micro_usdc,
            "provider_id": provider_id,
        })

class BillingSessionClosed(DomainEvent):
    def __init__(self, session_id: str, total_consumed: int):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "total_consumed": total_consumed})

class BillingSessionSettled(DomainEvent):
    def __init__(self, session_id: str, tx_hash: str, amount_paid: int):
        super().__init__(aggregate_id=session_id, data={
            "session_id": session_id, "tx_hash": tx_hash, "amount_paid": amount_paid})
