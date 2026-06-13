"""Health check schemas."""
from pydantic import BaseModel
from typing import Dict


class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, str]
