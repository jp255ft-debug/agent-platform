"""Simulador do IonetClient para desenvolvimento/testes sem API real da io.net.

Retorna dados realistas de GPU hardware, preços e deploys simulados.
Ativado automaticamente quando IO_NET_SIMULATOR=true no .env ou quando
nenhuma credencial válida da io.net está configurada.
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from app.infrastructure.depin.ionet_models import (
    DeploymentStatus,
    DeployResponse,
    GPUHardware,
    HardwareFilter,
    PriceResponse,
)

# ─── Dados mockados de GPUs realistas ────────────────────────────────────────

MOCK_GPUS: list[dict] = [
    {
        "id": "gpu-rtx4090-001",
        "name": "RTX 4090",
        "num_cards": 1,
        "supplier": "internal",
        "sold_out": False,
        "price": 0.79,
        "vram_per_card": 24,
        "location": "US-East",
        "vcpu": 16,
        "memory": 64,
        "storage": 500,
        "interconnect": "pcie",
        "nvlink": False,
    },
    {
        "id": "gpu-rtx4090-4x-002",
        "name": "RTX 4090",
        "num_cards": 4,
        "supplier": "internal",
        "sold_out": False,
        "price": 2.85,
        "vram_per_card": 24,
        "location": "US-East",
        "vcpu": 64,
        "memory": 256,
        "storage": 2000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-a100-003",
        "name": "A100 80GB",
        "num_cards": 1,
        "supplier": "external",
        "sold_out": False,
        "price": 2.50,
        "vram_per_card": 80,
        "location": "US-West",
        "vcpu": 32,
        "memory": 128,
        "storage": 1000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-a100-8x-004",
        "name": "A100 80GB",
        "num_cards": 8,
        "supplier": "external",
        "sold_out": True,
        "price": 18.00,
        "vram_per_card": 80,
        "location": "US-West",
        "vcpu": 256,
        "memory": 1024,
        "storage": 8000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-h100-005",
        "name": "H100 80GB HBM3",
        "num_cards": 1,
        "supplier": "external",
        "sold_out": False,
        "price": 4.50,
        "vram_per_card": 80,
        "location": "EU-West",
        "vcpu": 32,
        "memory": 128,
        "storage": 1000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-h100-8x-006",
        "name": "H100 80GB HBM3",
        "num_cards": 8,
        "supplier": "external",
        "sold_out": False,
        "price": 32.00,
        "vram_per_card": 80,
        "location": "EU-West",
        "vcpu": 256,
        "memory": 1024,
        "storage": 8000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-rtx4090-sa-007",
        "name": "RTX 4090",
        "num_cards": 2,
        "supplier": "internal",
        "sold_out": False,
        "price": 1.50,
        "vram_per_card": 24,
        "location": "SA-East",
        "vcpu": 32,
        "memory": 128,
        "storage": 1000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-l40s-008",
        "name": "L40S 48GB",
        "num_cards": 1,
        "supplier": "internal",
        "sold_out": False,
        "price": 1.20,
        "vram_per_card": 48,
        "location": "US-East",
        "vcpu": 16,
        "memory": 64,
        "storage": 500,
        "interconnect": "pcie",
        "nvlink": False,
    },
    {
        "id": "gpu-a100-sa-009",
        "name": "A100 80GB",
        "num_cards": 2,
        "supplier": "external",
        "sold_out": False,
        "price": 4.80,
        "vram_per_card": 80,
        "location": "SA-East",
        "vcpu": 64,
        "memory": 256,
        "storage": 2000,
        "interconnect": "nvlink",
        "nvlink": True,
    },
    {
        "id": "gpu-rtx6000-010",
        "name": "RTX 6000 Ada",
        "num_cards": 1,
        "supplier": "internal",
        "sold_out": True,
        "price": 1.00,
        "vram_per_card": 48,
        "location": "US-East",
        "vcpu": 16,
        "memory": 64,
        "storage": 500,
        "interconnect": "pcie",
        "nvlink": False,
    },
]


class IonetSimulator:
    """
    Simulador do cliente io.net para desenvolvimento.

    Retorna dados mockados realistas sem chamar a API externa.
    Útil para testar o fluxo completo de GPU leasing sem credenciais reais.
    """

    def __init__(self):
        self._deployments: dict[str, dict] = {}

    # ─── VMaaS — GPU Cluster Management ──────────────────────────────────────

    async def list_gpus(self, filters: Optional[HardwareFilter] = None) -> list[GPUHardware]:
        """Simula listagem de GPUs disponíveis."""
        gpus = [GPUHardware(**h) for h in MOCK_GPUS]

        if filters:
            if filters.search:
                gpus = [g for g in gpus if filters.search.lower() in g.name.lower()]
            if filters.regions:
                gpus = [g for g in gpus if g.location in filters.regions]
            if filters.min_gpu_memory is not None:
                gpus = [g for g in gpus if g.vram_per_card >= filters.min_gpu_memory]
            if filters.max_gpu_memory is not None:
                gpus = [g for g in gpus if g.vram_per_card <= filters.max_gpu_memory]
            if filters.min_vcpu is not None:
                gpus = [g for g in gpus if g.vcpu >= filters.min_vcpu]
            if filters.max_vcpu is not None:
                gpus = [g for g in gpus if g.vcpu <= filters.max_vcpu]
            if filters.min_memory is not None:
                gpus = [g for g in gpus if g.memory >= filters.min_memory]
            if filters.max_memory is not None:
                gpus = [g for g in gpus if g.memory <= filters.max_memory]
            if filters.min_storage is not None:
                gpus = [g for g in gpus if g.storage >= filters.min_storage]
            if filters.max_storage is not None:
                gpus = [g for g in gpus if g.storage <= filters.max_storage]
            if filters.supplier:
                gpus = [g for g in gpus if g.supplier == filters.supplier]

        return gpus

    async def get_price(self, hardware_id: str, duration_hours: int, currency: str = "usdc") -> PriceResponse:
        """Simula cálculo de preço."""
        gpu = next((g for g in MOCK_GPUS if g["id"] == hardware_id), None)
        if not gpu:
            raise ValueError(f"Hardware ID '{hardware_id}' not found")

        base_cost = gpu["price"] * duration_hours
        ionet_fee = base_cost * 0.10  # 10% fee

        return PriceResponse(
            total_cost_usdc=round(base_cost + ionet_fee, 2),
            ionet_fee=round(ionet_fee, 2),
            ionet_fee_percent=10.0,
            replica_count=1,
            gpus_per_vm=gpu["num_cards"],
            available_replica_count=[1, 2, 4],
            discount=0.0,
            currency_conversion_fee=0.0,
            currency_conversion_fee_percent=0.0,
        )

    async def deploy_cluster(self, hardware_id: str, duration_hours: int, replica_count: int = 1) -> DeployResponse:
        """Simula deploy de cluster GPU."""
        gpu = next((g for g in MOCK_GPUS if g["id"] == hardware_id), None)
        if not gpu:
            raise ValueError(f"Hardware ID '{hardware_id}' not found")
        if gpu["sold_out"]:
            raise RuntimeError(f"Hardware '{gpu['name']}' is sold out")

        deployment_id = f"sim-dep-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        self._deployments[deployment_id] = {
            "deployment_id": deployment_id,
            "status": "provisioning",
            "hardware_id": hardware_id,
            "replica_count": replica_count,
            "created_at": now,
            "expires_at": now + timedelta(hours=duration_hours),
            "gpu_model": gpu["name"],
            "gpu_count": gpu["num_cards"] * replica_count,
        }

        return DeployResponse(
            deployment_id=deployment_id,
            status="provisioning",
            message=f"Cluster provisioning started: {replica_count}x {gpu['name']} for {duration_hours}h",
        )

    async def extend_cluster(self, deployment_id: str, additional_hours: int) -> dict[str, Any]:
        """Simula extensão de cluster."""
        dep = self._deployments.get(deployment_id)
        if not dep:
            raise ValueError(f"Deployment '{deployment_id}' not found")

        dep["expires_at"] = dep["expires_at"] + timedelta(hours=additional_hours)
        return {
            "deployment_id": deployment_id,
            "new_expires_at": dep["expires_at"].isoformat(),
        }

    async def destroy_cluster(self, deployment_id: str) -> dict[str, Any]:
        """Simula destruição de cluster."""
        dep = self._deployments.get(deployment_id)
        if not dep:
            raise ValueError(f"Deployment '{deployment_id}' not found")

        dep["status"] = "terminated"
        return {"status": "terminated"}

    async def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        """Simula consulta de status de deployment."""
        dep = self._deployments.get(deployment_id)
        if not dep:
            raise ValueError(f"Deployment '{deployment_id}' not found")

        # Simula transição de status após alguns segundos
        if dep["status"] == "provisioning":
            dep["status"] = "running"

        return DeploymentStatus(**dep)

    # ─── CaaS — Container Deployment ─────────────────────────────────────────

    async def deploy_container(
        self,
        image: str,
        gpu_count: int = 1,
        env_vars: Optional[dict[str, str]] = None,
        command: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Simula deploy de container."""
        return {
            "deployment_id": f"sim-container-{uuid.uuid4().hex[:12]}",
            "status": "running",
        }

    # ─── IO Intelligence — AI Agents & Inference ─────────────────────────────

    async def list_models(self, supports_attestation: bool = False) -> list[dict[str, Any]]:
        """Simula listagem de modelos de IA."""
        models = [
            {"id": "llama-3-70b", "name": "Llama 3 70B", "supports_attestation": True},
            {"id": "llama-3-8b", "name": "Llama 3 8B", "supports_attestation": True},
            {"id": "mixtral-8x7b", "name": "Mixtral 8x7B", "supports_attestation": False},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "supports_attestation": False},
        ]
        if supports_attestation:
            models = [m for m in models if m["supports_attestation"]]
        return models

    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """Simula chat completion."""
        return {
            "id": f"sim-chat-{uuid.uuid4().hex[:12]}",
            "choices": [
                {
                    "message": {
                        "content": f"[SIMULATED] Response from {model_id}. "
                                   f"This is a simulated response for development/testing."
                    }
                }
            ],
        }

    async def get_attestation(self, model_id: str, nonce: str) -> dict[str, Any]:
        """Simula atestação de GPU."""
        return {
            "attestation": f"0x{uuid.uuid4().hex}",
            "model_id": model_id,
        }
