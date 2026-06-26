"""GPU leasing Pydantic schemas."""

from pydantic import BaseModel, Field


class GPUHardwareResponse(BaseModel):
    """GPU hardware listing response."""
    id: str
    model: str
    gpu_count: int
    vram_gb: int
    total_vram_gb: int
    price_per_hour_usdc: float
    location: str
    is_available: bool
    vcpu: int
    memory_gb: int
    storage_gb: int

    class Config:
        from_attributes = True


class GPULeaseRequest(BaseModel):
    """Request to lease a GPU."""
    hardware_id: str = Field(..., description="io.net hardware ID")
    duration_hours: int = Field(..., ge=1, le=720, description="Lease duration in hours (max 30 days)")
    gpu_count: int | None = Field(default=1, ge=1, le=8, description="Number of GPUs to lease")
    max_budget_usdc: float | None = Field(
        default=None, ge=0, description="Maximum budget in USDC (optional)"
    )


class GPULeaseResponse(BaseModel):
    """GPU lease response."""
    lease_id: str
    deployment_id: str | None = None
    status: str
    gpu_model: str | None = None
    gpu_count: int | None = None
    duration_hours: int | None = None
    total_cost_usdc: float | None = None
    ionet_fee_usdc: float | None = None
    remaining_hours: float | None = None
    is_active: bool = False
    created_at: str | None = None
    activated_at: str | None = None
    expires_at: str | None = None


class ExtendLeaseRequest(BaseModel):
    """Request to extend a GPU lease."""
    additional_hours: int = Field(..., ge=1, le=720, description="Additional hours to extend")


class ExtendLeaseResponse(BaseModel):
    """Response after extending a GPU lease."""
    lease_id: str
    status: str
    new_expires_at: str
    new_duration_hours: int


class GPUSpecsResponse(BaseModel):
    """Detailed GPU specifications."""
    hardware_id: str
    model: str
    vram_per_card_gb: int
    num_cards: int
    total_vram_gb: int
    vcpu: int
    memory_gb: int
    storage_gb: int
    interconnect: str | None = None
    nvlink: bool = False
    price_per_hour_usdc: float
    location: str
    supplier: str
    is_available: bool
