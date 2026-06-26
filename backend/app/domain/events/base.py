"""Base domain event."""
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class DomainEvent:
    def __init__(self, aggregate_id: str, data: dict[str, Any] | None = None, correlation_id: str | None = None):
        self.event_id: str = str(uuid4())
        self.aggregate_id: str = aggregate_id
        self.occurred_at: datetime = datetime.now(UTC)
        self.data: dict[str, Any] = data or {}
        self.correlation_id: str | None = correlation_id

    def event_type(self) -> str:
        return self.__class__.__name__

    def to_dict(self) -> dict[str, Any]:
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
