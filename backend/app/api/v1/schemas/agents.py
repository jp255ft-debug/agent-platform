"""Agent schemas."""
from pydantic import BaseModel, Field
from typing import Optional


class AgentCreate(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier")
    owner_address: str = Field(..., description="Ethereum address of the agent owner")
    delegation_address: Optional[str] = Field(None, description="Optional EIP-7702 delegation address")


class AgentResponse(BaseModel):
    agent_id: str
    owner_address: str
    delegation_address: Optional[str] = None
    delegation_active: bool = False
    reputation_score: int = 100
    version: int = 0

    class Config:
        from_attributes = True


class AgentDelegateRequest(BaseModel):
    delegate_address: str = Field(..., description="Address to delegate to")
    expires_at: str = Field(..., description="ISO 8601 expiration timestamp")


class AgentReputationUpdate(BaseModel):
    new_score: int = Field(..., ge=0, le=100, description="New reputation score (0-100)")
    reason: str = Field(..., description="Reason for reputation change")
