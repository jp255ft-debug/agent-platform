"""io.net API data models."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GPUHardware:
    """GPU hardware listing from io.net VMaaS."""
    id: str
    name: str
    num_cards: int
    supplier: str
    price: float
    vram_per_card: int
    location: str
    vcpu: int
    memory: int
    storage: int
    sold_out: bool = False
    interconnect: str | None = None
    nvlink: bool = False
    deploy_id: str | None = None

    @classmethod
    def from_api(cls, **kwargs) -> "GPUHardware":
        """Create GPUHardware from API response, ignoring unknown fields."""
        known_fields = {
            "id", "name", "num_cards", "supplier", "sold_out", "price",
            "vram_per_card", "location", "vcpu", "memory", "storage",
            "interconnect", "nvlink", "deploy_id",
        }
        filtered = {k: v for k, v in kwargs.items() if k in known_fields}
        return cls(**filtered)

    @property
    def total_vram_gb(self) -> int:
        return self.vram_per_card * self.num_cards

    @property
    def is_available(self) -> bool:
        return not self.sold_out


@dataclass
class PriceResponse:
    """Price calculation response from io.net."""
    total_cost_usdc: float
    ionet_fee: float
    ionet_fee_percent: float
    replica_count: int
    gpus_per_vm: int
    available_replica_count: list[int]
    discount: float = 0.0
    currency_conversion_fee: float = 0.0
    currency_conversion_fee_percent: float = 0.0


@dataclass
class DeployResponse:
    """Deployment response from io.net VMaaS."""
    deployment_id: str
    status: str
    message: str | None = None


@dataclass
class DeploymentStatus:
    """Status of an active deployment."""
    deployment_id: str
    status: str  # provisioning, running, stopping, terminated
    hardware_id: str
    replica_count: int
    created_at: datetime
    expires_at: datetime
    gpu_model: str
    gpu_count: int


@dataclass
class HardwareFilter:
    """Filter parameters for listing GPU hardware."""
    search: str | None = None
    regions: list[str] | None = None
    min_gpu_memory: int | None = None
    max_gpu_memory: int | None = None
    min_vcpu: int | None = None
    max_vcpu: int | None = None
    min_memory: int | None = None
    max_memory: int | None = None
    min_storage: int | None = None
    max_storage: int | None = None
    supplier: str | None = None  # internal, external

    def to_dict(self) -> dict:
        """Convert filter to query parameters dict."""
        result = {}
        if self.search:
            result["search"] = self.search
        if self.regions:
            result["regions"] = ",".join(self.regions)
        if self.min_gpu_memory is not None:
            result["min_gpu_memory"] = str(self.min_gpu_memory)
        if self.max_gpu_memory is not None:
            result["max_gpu_memory"] = str(self.max_gpu_memory)
        if self.min_vcpu is not None:
            result["min_vcpu"] = str(self.min_vcpu)
        if self.max_vcpu is not None:
            result["max_vcpu"] = str(self.max_vcpu)
        if self.min_memory is not None:
            result["min_memory"] = str(self.min_memory)
        if self.max_memory is not None:
            result["max_memory"] = str(self.max_memory)
        if self.min_storage is not None:
            result["min_storage"] = str(self.min_storage)
        if self.max_storage is not None:
            result["max_storage"] = str(self.max_storage)
        if self.supplier:
            result["supplier"] = self.supplier
        return result
