"""Eventos de domínio para o agregado ProviderAggregate (DePIN).

Define os eventos do ciclo de vida de provedores de recursos computacionais
em redes DePIN, incluindo registro, telemetria, staking e slashing.
"""
from app.domain.events.base import DomainEvent


class ProviderRegistered(DomainEvent):
    """Evento disparado quando um novo provedor DePIN é registrado.

    Data:
        - owner_address: str — Endereço da wallet do operador do nó
        - gpu_specs: dict — Especificações da GPU (modelo, VRAM, TFLOPS, etc.)
        - registered_at: str — ISO timestamp do registro
    """
    pass


class ProviderStatusChanged(DomainEvent):
    """Evento disparado quando o status do provedor muda.

    Data:
        - old_status: str — Status anterior (pending, active, suspended, slashed, inactive)
        - new_status: str — Novo status
        - reason: str — Motivo da mudança (activation, suspension, slashing, etc.)
    """
    pass


class HealthReported(DomainEvent):
    """Evento disparado quando um relatório de telemetria é recebido do nó.

    Data:
        - uptime_seconds: int — Segundos de uptime desde o último relatório
        - is_online: bool — Se o nó está online
        - total_uptime_seconds: int — Uptime total acumulado
        - reported_at: str — ISO timestamp do relatório
        - gpu_stats: dict | None — Métricas da GPU (utilização, temperatura, etc.)
    """
    pass


class SlashingApplied(DomainEvent):
    """Evento disparado quando uma penalidade é aplicada ao provedor.

    Data:
        - penalty_percent: int — Percentual do stake penalizado (0-100)
        - slashed_amount: int — Quantidade em micro USDC queimada
        - remaining_stake: int — Stake restante após slashing
        - new_reputation: int — Novo score de reputação (0-100)
        - reason: str — Motivo (compute_fraud, downtime_exceeded, etc.)
        - status: str — Status do provedor após slashing
    """
    pass


class ProviderStaked(DomainEvent):
    """Evento disparado quando stake é adicionado ao provedor.

    Data:
        - amount: int — Quantidade em micro USDC adicionada ao stake
        - total_staked: int — Total acumulado de stake
    """
    pass


class ProviderUnstaked(DomainEvent):
    """Evento disparado quando stake é removido do provedor.

    Data:
        - amount: int — Quantidade em micro USDC removida
        - total_staked: int — Total restante de stake
    """
    pass


class GPUSpecsUpdated(DomainEvent):
    """Evento disparado quando as especificações da GPU são atualizadas.

    Data:
        - old_specs: dict | None — Especificações anteriores
        - new_specs: dict — Novas especificações
    """
    pass


class ProviderJobCompleted(DomainEvent):
    """Evento disparado quando um job de computação é concluído no provedor.

    Data:
        - session_id: str — ID da sessão de billing associada
        - agent_id: str — ID do agente consumidor
        - success: bool — Se o job foi concluído com sucesso
        - compute_time_seconds: int — Tempo total de computação
        - proof_hash: str | None — Hash da prova de computação (se aplicável)
    """
    pass
