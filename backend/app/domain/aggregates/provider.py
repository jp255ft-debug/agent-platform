"""ProviderAggregate — Agregado DDD para provedores de GPU em redes DePIN.

Este agregado gerencia o ciclo de vida completo de um provedor de recursos
computacionais em uma rede DePIN, incluindo:
- Registro e especificações de hardware (GPU)
- Stake mínimo para ativação
- Telemetria e health checks
- Slashing por mau comportamento
- Reputação baseada em jobs concluídos
"""
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.domain.events.base import DomainEvent
from app.domain.events.provider_events import (
    GPUSpecsUpdated,
    HealthReported,
    ProviderJobCompleted,
    ProviderRegistered,
    ProviderStaked,
    ProviderStatusChanged,
    ProviderUnstaked,
    SlashingApplied,
)


class ProviderStatus(Enum):
    """Status do ciclo de vida do provedor DePIN.

    Fluxo de transição:
        PENDING ──(stake + validação)──▶ ACTIVE ──(inatividade)──▶ INACTIVE
                                              │
                                              ├──(fraude)──▶ SLASHED
                                              └──(suspensão)──▶ SUSPENDED ──▶ ACTIVE
    """
    PENDING = "pending"           # Aguardando validação inicial
    ACTIVE = "active"             # Operacional e aceitando jobs
    SUSPENDED = "suspended"       # Suspenso temporariamente
    SLASHED = "slashed"           # Penalizado com perda de stake
    INACTIVE = "inactive"         # Offline por inatividade prolongada


@dataclass
class GPUSpecs:
    """Especificações técnicas da GPU oferecida pelo provedor.

    Value Object imutável — qualquer alteração gera um novo evento GPUSpecsUpdated.
    """
    model: str                     # ex: "NVIDIA H100", "A100", "RTX 4090"
    vram_gb: int                   # Memória VRAM em GB
    tflops_fp16: float             # Desempenho FP16 em TFLOPS
    tflops_fp32: float             # Desempenho FP32 em TFLOPS
    cuda_cores: int                # Número de CUDA cores
    memory_bandwidth_gbps: float   # Largura de banda em GB/s
    driver_version: str            # Versão do driver NVIDIA
    price_per_tflops_hour: float   # Preço em USDC por TFLOPS/hora

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "vram_gb": self.vram_gb,
            "tflops_fp16": self.tflops_fp16,
            "tflops_fp32": self.tflops_fp32,
            "cuda_cores": self.cuda_cores,
            "memory_bandwidth_gbps": self.memory_bandwidth_gbps,
            "driver_version": self.driver_version,
            "price_per_tflops_hour": self.price_per_tflops_hour,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GPUSpecs":
        return GPUSpecs(
            model=data.get("model", "unknown"),
            vram_gb=data.get("vram_gb", 0),
            tflops_fp16=data.get("tflops_fp16", 0.0),
            tflops_fp32=data.get("tflops_fp32", 0.0),
            cuda_cores=data.get("cuda_cores", 0),
            memory_bandwidth_gbps=data.get("memory_bandwidth_gbps", 0.0),
            driver_version=data.get("driver_version", "unknown"),
            price_per_tflops_hour=data.get("price_per_tflops_hour", 0.0),
        )


# Stake mínimo exigido para ativação do provedor (10 USDC em micro USDC)
MIN_STAKE_REQUIRED = 10_000_000


@dataclass
class ProviderAggregate:
    """Agregado de Provedor DePIN.

    Gerencia o ciclo de vida de um nó provedor de recursos computacionais,
    incluindo registro, telemetria, staking, slashing e reputação.

    Invariantes:
    - Um provedor só pode estar ACTIVE se tiver stake >= MIN_STAKE_REQUIRED
    - O status segue o fluxo: PENDING → ACTIVE → SUSPENDED/SLASHED → INACTIVE
    - O score de reputação nunca pode ser negativo (0-100)
    - Slashing reduz stake e reputação proporcionalmente
    """
    provider_id: str
    owner_address: str
    gpu_specs: GPUSpecs | None = None
    status: ProviderStatus = ProviderStatus.PENDING
    reputation_score: int = 100       # 0-100, começa em 100
    staked_amount: int = 0            # Em micro USDC
    total_uptime_seconds: int = 0
    total_jobs_completed: int = 0
    total_jobs_failed: int = 0
    last_health_report: datetime | None = None
    registered_at: datetime | None = None
    updated_at: datetime | None = None
    version: int = 0
    _changes: list[DomainEvent] = field(default_factory=list)

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @staticmethod
    def register(
        provider_id: str,
        owner_address: str,
        gpu_specs: GPUSpecs,
    ) -> "ProviderAggregate":
        """Registra um novo provedor DePIN.

        O provedor nasce no status PENDING e precisa de stake mínimo
        para ser ativado.
        """
        now = datetime.now(UTC)
        provider = ProviderAggregate(
            provider_id=provider_id,
            owner_address=owner_address,
            gpu_specs=gpu_specs,
            status=ProviderStatus.PENDING,
            registered_at=now,
            updated_at=now,
        )
        event = ProviderRegistered(
            aggregate_id=provider_id,
            data={
                "owner_address": owner_address,
                "gpu_specs": gpu_specs.to_dict(),
                "registered_at": now.isoformat(),
            }
        )
        provider._apply(event)
        provider._changes.append(event)
        return provider

    # =========================================================================
    # Comandos de Ciclo de Vida
    # =========================================================================

    def activate(self) -> None:
        """Ativa o provedor para começar a aceitar jobs.

        Requer:
        - Status atual deve ser PENDING
        - Stake >= MIN_STAKE_REQUIRED
        """
        if self.status != ProviderStatus.PENDING:
            raise ValueError(
                f"Cannot activate provider in status: {self.status.value}"
            )
        if self.staked_amount < MIN_STAKE_REQUIRED:
            raise ValueError(
                f"Stake {self.staked_amount} below minimum required "
                f"{MIN_STAKE_REQUIRED}"
            )

        event = ProviderStatusChanged(
            aggregate_id=self.provider_id,
            data={
                "old_status": self.status.value,
                "new_status": ProviderStatus.ACTIVE.value,
                "reason": "activation",
            }
        )
        self._apply(event)
        self._changes.append(event)

    def suspend(self, reason: str = "suspension") -> None:
        """Suspende o provedor temporariamente."""
        if self.status != ProviderStatus.ACTIVE:
            raise ValueError(
                f"Cannot suspend provider in status: {self.status.value}"
            )

        event = ProviderStatusChanged(
            aggregate_id=self.provider_id,
            data={
                "old_status": self.status.value,
                "new_status": ProviderStatus.SUSPENDED.value,
                "reason": reason,
            }
        )
        self._apply(event)
        self._changes.append(event)

    def mark_inactive(self, reason: str = "prolonged_downtime") -> None:
        """Marca o provedor como inativo por inatividade prolongada."""
        if self.status not in [ProviderStatus.ACTIVE, ProviderStatus.SUSPENDED]:
            raise ValueError(
                f"Cannot mark inactive from status: {self.status.value}"
            )

        event = ProviderStatusChanged(
            aggregate_id=self.provider_id,
            data={
                "old_status": self.status.value,
                "new_status": ProviderStatus.INACTIVE.value,
                "reason": reason,
            }
        )
        self._apply(event)
        self._changes.append(event)

    # =========================================================================
    # Telemetria
    # =========================================================================

    def report_health(
        self,
        uptime_seconds: int,
        is_online: bool,
        gpu_stats: dict[str, Any] | None = None,
    ) -> None:
        """Recebe relatório de telemetria do nó via gRPC.

        Args:
            uptime_seconds: Segundos de uptime desde o último relatório
            is_online: Se o nó está online e responsivo
            gpu_stats: Métricas opcionais da GPU (utilização, temperatura, etc.)
        """
        if self.status not in [ProviderStatus.ACTIVE, ProviderStatus.PENDING]:
            return  # Ignora health reports se não estiver ativo

        self.total_uptime_seconds += uptime_seconds if is_online else 0
        self.last_health_report = datetime.now(UTC)

        event = HealthReported(
            aggregate_id=self.provider_id,
            data={
                "uptime_seconds": uptime_seconds,
                "is_online": is_online,
                "total_uptime_seconds": self.total_uptime_seconds,
                "reported_at": self.last_health_report.isoformat(),
                "gpu_stats": gpu_stats,
            }
        )
        self._apply(event)
        self._changes.append(event)

    # =========================================================================
    # Slashing e Penalidades
    # =========================================================================

    def apply_slashing(self, penalty_percent: int, reason: str) -> None:
        """Aplica penalidade ao provedor por mau comportamento.

        O slashing reduz tanto o stake quanto a reputação proporcionalmente.
        Se a reputação cair abaixo de 30 ou o stake chegar a 0,
        o provedor é marcado como SLASHED.

        Args:
            penalty_percent: Percentual do stake a ser queimado (0-100)
            reason: Motivo (compute_fraud, downtime_exceeded, etc.)
        """
        if self.status == ProviderStatus.SLASHED:
            return  # Já foi slashed, não aplica novamente

        if not 0 <= penalty_percent <= 100:
            raise ValueError(f"Penalty percent must be 0-100, got {penalty_percent}")

        slashed_amount = int(self.staked_amount * (penalty_percent / 100))
        self.staked_amount -= slashed_amount
        self.reputation_score = max(0, self.reputation_score - penalty_percent)

        new_status = self.status.value
        if self.reputation_score < 30 or self.staked_amount < MIN_STAKE_REQUIRED:
            self.status = ProviderStatus.SLASHED
            new_status = ProviderStatus.SLASHED.value

        event = SlashingApplied(
            aggregate_id=self.provider_id,
            data={
                "penalty_percent": penalty_percent,
                "slashed_amount": slashed_amount,
                "remaining_stake": self.staked_amount,
                "new_reputation": self.reputation_score,
                "reason": reason,
                "status": new_status,
            }
        )
        self._apply(event)
        self._changes.append(event)

    # =========================================================================
    # Staking
    # =========================================================================

    def stake(self, amount: int) -> None:
        """Adiciona stake ao provedor.

        Args:
            amount: Quantidade em micro USDC
        """
        if amount <= 0:
            raise ValueError(f"Stake amount must be positive, got {amount}")

        self.staked_amount += amount

        event = ProviderStaked(
            aggregate_id=self.provider_id,
            data={
                "amount": amount,
                "total_staked": self.staked_amount,
            }
        )
        self._apply(event)
        self._changes.append(event)

    def unstake(self, amount: int) -> None:
        """Remove stake do provedor.

        Args:
            amount: Quantidade em micro USDC

        Raises:
            ValueError: Se amount > staked_amount ou se o stake restante
                       ficar abaixo do mínimo exigido
        """
        if amount <= 0:
            raise ValueError(f"Unstake amount must be positive, got {amount}")
        if amount > self.staked_amount:
            raise ValueError(
                f"Insufficient staked amount: {amount} > {self.staked_amount}"
            )
        if self.staked_amount - amount < MIN_STAKE_REQUIRED:
            raise ValueError(
                f"Cannot unstake below minimum required {MIN_STAKE_REQUIRED}"
            )

        self.staked_amount -= amount

        event = ProviderUnstaked(
            aggregate_id=self.provider_id,
            data={
                "amount": amount,
                "total_staked": self.staked_amount,
            }
        )
        self._apply(event)
        self._changes.append(event)

    # =========================================================================
    # GPU Specs
    # =========================================================================

    def update_gpu_specs(self, new_specs: GPUSpecs) -> None:
        """Atualiza as especificações da GPU.

        Args:
            new_specs: Novas especificações da GPU

        Raises:
            ValueError: Se o provedor estiver SLASHED
        """
        if self.status == ProviderStatus.SLASHED:
            raise ValueError("Cannot update specs for slashed provider")

        old_specs = self.gpu_specs.to_dict() if self.gpu_specs else None
        self.gpu_specs = new_specs

        event = GPUSpecsUpdated(
            aggregate_id=self.provider_id,
            data={
                "old_specs": old_specs,
                "new_specs": new_specs.to_dict(),
            }
        )
        self._apply(event)
        self._changes.append(event)

    # =========================================================================
    # Jobs
    # =========================================================================

    def record_job_completion(
        self,
        session_id: str,
        agent_id: str,
        success: bool,
        compute_time_seconds: int,
        proof_hash: str | None = None,
    ) -> None:
        """Registra a conclusão de um job de computação.

        Jobs bem-sucedidos aumentam a reputação lentamente (max 100).
        Jobs falhos reduzem a reputação.

        Args:
            session_id: ID da sessão de billing
            agent_id: ID do agente consumidor
            success: Se o job foi concluído com sucesso
            compute_time_seconds: Tempo total de computação
            proof_hash: Hash da prova de computação (se aplicável)

        Raises:
            ValueError: Se o provedor não estiver ACTIVE
        """
        if self.status != ProviderStatus.ACTIVE:
            raise ValueError(
                f"Cannot record job completion for provider in status: {self.status.value}"
            )

        event = ProviderJobCompleted(
            aggregate_id=self.provider_id,
            data={
                "session_id": session_id,
                "agent_id": agent_id,
                "success": success,
                "compute_time_seconds": compute_time_seconds,
                "proof_hash": proof_hash,
            }
        )
        self._apply(event)
        self._changes.append(event)

    # =========================================================================
    # Queries
    # =========================================================================

    @property
    def is_active(self) -> bool:
        """Verifica se o provedor está ativo e pode aceitar jobs."""
        return self.status == ProviderStatus.ACTIVE

    @property
    def uptime_percentage(self) -> float:
        """Calcula o percentual de uptime baseado em jobs."""
        total_jobs = self.total_jobs_completed + self.total_jobs_failed
        if total_jobs == 0:
            return 0.0
        return (self.total_jobs_completed / total_jobs) * 100.0

    @property
    def can_be_activated(self) -> bool:
        """Verifica se o provedor pode ser ativado (stake suficiente)."""
        return self.staked_amount >= MIN_STAKE_REQUIRED

    # =========================================================================
    # Event Sourcing
    # =========================================================================

    def _apply(self, event: DomainEvent) -> None:
        """Reconstrói o estado do agregado a partir de um evento."""
        if isinstance(event, ProviderRegistered):
            owner_addr: str | None = event.data.get("owner_address")
            if owner_addr is not None:
                self.owner_address = owner_addr
            specs_data = event.data.get("gpu_specs", {})
            if specs_data:
                self.gpu_specs = GPUSpecs.from_dict(specs_data)
            registered_at_str: str = event.data.get("registered_at", datetime.now(UTC).isoformat())
            self.registered_at = datetime.fromisoformat(registered_at_str)

        elif isinstance(event, ProviderStatusChanged):
            new_status: str = event.data.get("new_status", self.status.value)
            self.status = ProviderStatus(new_status)

        elif isinstance(event, HealthReported):
            self.total_uptime_seconds = event.data.get(
                "total_uptime_seconds", self.total_uptime_seconds
            )
            reported_at = event.data.get("reported_at")
            if reported_at:
                self.last_health_report = datetime.fromisoformat(reported_at)

        elif isinstance(event, SlashingApplied):
            self.staked_amount = event.data.get("remaining_stake", self.staked_amount)
            self.reputation_score = event.data.get("new_reputation", self.reputation_score)
            status_str = event.data.get("status", self.status.value)
            self.status = ProviderStatus(status_str)

        elif isinstance(event, ProviderStaked):
            self.staked_amount = event.data.get("total_staked", self.staked_amount)

        elif isinstance(event, ProviderUnstaked):
            self.staked_amount = event.data.get("total_staked", self.staked_amount)

        elif isinstance(event, GPUSpecsUpdated):
            specs_data = event.data.get("new_specs", {})
            if specs_data:
                self.gpu_specs = GPUSpecs.from_dict(specs_data)

        elif isinstance(event, ProviderJobCompleted):
            if event.data.get("success", False):
                self.total_jobs_completed += 1
                self.reputation_score = min(100, self.reputation_score + 1)
            else:
                self.total_jobs_failed += 1
                self.reputation_score = max(0, self.reputation_score - 2)

        self.version += 1
        self.updated_at = datetime.now(UTC)

    def get_changes(self) -> list[DomainEvent]:
        """Retorna eventos não persistidos desde o último clear_changes()."""
        return self._changes.copy()

    def clear_changes(self) -> None:
        """Limpa eventos após persistência bem-sucedida."""
        self._changes.clear()
