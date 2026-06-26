"""Kafka event producer for publishing domain events."""
import json
import logging

from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.domain.events.base import DomainEvent

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """Publishes domain events to Kafka topics."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

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

    async def publish_event(self, event: DomainEvent, topic: str | None = None) -> None:
        """Publish a domain event to a Kafka topic.

        Uses aggregate_id as the partition key to guarantee event ordering
        per aggregate across all events in the same topic.
        """
        if not self._producer:
            raise RuntimeError("Kafka producer not started")

        topic = topic or event.event_type()
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type(),
            "aggregate_id": event.aggregate_id,
            "occurred_at": event.occurred_at.isoformat(),
            "data": event.data,
        }
        # Propagate correlation_id if present on the event
        if hasattr(event, "correlation_id") and event.correlation_id:
            payload["correlation_id"] = event.correlation_id

        await self._producer.send_and_wait(
            topic,
            payload,
            key=event.aggregate_id.encode("utf-8"),
        )

    async def publish_events(self, events: list[DomainEvent], topic: str | None = None) -> None:
        """Publish multiple domain events.

        All events are published with aggregate_id as partition key,
        ensuring causal ordering per aggregate across Kafka partitions.
        """
        for event in events:
            try:
                await self.publish_event(event, topic)
            except Exception as e:
                logger.error(
                    "Failed to publish event %s to topic %s: %s",
                    event.event_id, topic or event.event_type(), e,
                )
