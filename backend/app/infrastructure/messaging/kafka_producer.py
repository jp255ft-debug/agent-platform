"""Kafka event producer for publishing domain events."""
import json
from typing import Optional
from aiokafka import AIOKafkaProducer
from app.core.config import settings
from app.domain.events.base import DomainEvent


class KafkaEventProducer:
    """Publishes domain events to Kafka topics."""

    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        """Initialize the Kafka producer."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id="agent-platform",
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await self._producer.start()

    async def stop(self) -> None:
        """Close the Kafka producer."""
        if self._producer:
            await self._producer.stop()

    async def publish_event(self, event: DomainEvent, topic: Optional[str] = None) -> None:
        """Publish a domain event to a Kafka topic."""
        if not self._producer:
            raise RuntimeError("Kafka producer not started")

        topic = topic or event.event_type()
        await self._producer.send_and_wait(topic, {
            "event_id": event.event_id,
            "event_type": event.event_type(),
            "aggregate_id": event.aggregate_id,
            "occurred_at": event.occurred_at.isoformat(),
            "data": event.data,
        })

    async def publish_events(self, events: list[DomainEvent], topic: Optional[str] = None) -> None:
        """Publish multiple domain events."""
        for event in events:
            await self.publish_event(event, topic)
