"""Base domain event."""
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, Any, Optional

class DomainEvent:
    def __init__(self, aggregate_id: str, data: Dict[str, Any] | None = None, correlation_id: Optional[str] = None):
        self.event_id: str = str(uuid4())
        self.aggregate_id: str = aggregate_id
        self.occurred_at: datetime = datetime.now(timezone.utc)
        self.data: Dict[str, Any] = data or {}
        self.correlation_id: Optional[str] = correlation_id

    def event_type(self) -> str:
        return self.__class__.__name__

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type(),
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at.isoformat(),
            "data": self.data,
        }
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        return result
