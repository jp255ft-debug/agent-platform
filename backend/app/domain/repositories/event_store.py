from typing import Protocol

from app.domain.events.base import DomainEvent


class EventStore(Protocol):
    async def append_events(self, stream_id: str, events: list[DomainEvent],
        expected_version: int | None = None) -> None: ...
    async def load_stream(self, stream_id: str) -> list[DomainEvent]: ...
    async def load_stream_from_version(self, stream_id: str, from_version: int) -> list[DomainEvent]: ...
