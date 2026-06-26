"""Resource consumption schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class ConsumeRequest(BaseModel):
    agent_id: str = Field(..., description="Agent identifier")
    resource_type: str = Field(..., description="Type of resource (e.g., 'compute', 'storage', 'bandwidth')")
    amount: int = Field(..., gt=0, description="Amount of resource to consume")
    x402_payment: dict = Field(..., description="x402 payment proof (signed receipt)")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for safe retries")


class ConsumeResponse(BaseModel):
    session_id: str
    total_consumed: int
    remaining_tokens: int
    status: str


class BillingSessionResponse(BaseModel):
    session_id: str
    agent_id: str
    resource_type: str
    total_consumed: int
    status: str
    version: int

    class Config:
        from_attributes = True
