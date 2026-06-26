"""Kafka event consumer for processing domain events."""
import json
from collections.abc import Callable, Coroutine

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.domain.events.base import DomainEvent


class KafkaEventConsumer:
    """Consumes domain events from Kafka topics."""

    def __init__(self, topics: list[str]):
        self._topics = topics
        self._consumer: AIOKafkaConsumer | None = None
        self._handlers: dict[str, list[Callable[[DomainEvent], Coroutine]]] = {}

    async def start(self) -> None:
        """Initialize the Kafka consumer."""
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda v: json.loads(v.decode()),
            auto_offset_reset="earliest",
        )
        await self._consumer.start()

    async def stop(self) -> None:
        """Close the Kafka consumer."""
        if self._consumer:
            await self._consumer.stop()

    def register_handler(
        self, event_type: str,
        handler: Callable[[DomainEvent], Coroutine],
    ) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def consume_loop(self) -> None:
        """Continuously consume messages from Kafka."""
        if not self._consumer:
            raise RuntimeError("Kafka consumer not started")

        async for msg in self._consumer:
            event_data = msg.value
            event_type = event_data.get("event_type", "")
            handlers = self._handlers.get(event_type, [])

            # Reconstruct domain event
            event = DomainEvent(
                aggregate_id=event_data.get("aggregate_id", ""),
                data=event_data.get("data", {}),
            )
            event.event_id = event_data.get("event_id", "")
            event.event_type = lambda: event_type

            for handler in handlers:
                await handler(event)
