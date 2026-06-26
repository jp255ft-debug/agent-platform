"""Unit tests for KafkaEventProducer."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.messaging.kafka_producer import KafkaEventProducer
from app.domain.events.base import DomainEvent


class SampleEvent(DomainEvent):
    """Concrete domain event for testing."""
    pass


@pytest.fixture
def mock_producer():
    """Create a mock AIOKafkaProducer."""
    producer = MagicMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_and_wait = AsyncMock()
    return producer


@pytest.fixture
def event_producer(mock_producer):
    """Create a KafkaEventProducer with mocked internals."""
    with patch("app.infrastructure.messaging.kafka_producer.AIOKafkaProducer", return_value=mock_producer):
        with patch("app.infrastructure.messaging.kafka_producer.settings") as mock_settings:
            mock_settings.KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
            producer = KafkaEventProducer()
            # Manually set the producer to avoid calling start()
            producer._producer = mock_producer
            return producer


class TestKafkaEventProducerInitialization:
    """Test KafkaEventProducer initialization."""

    def test_producer_starts_as_none(self):
        producer = KafkaEventProducer()
        assert producer._producer is None

    async def test_start_creates_producer(self, mock_producer):
        with patch("app.infrastructure.messaging.kafka_producer.AIOKafkaProducer", return_value=mock_producer) as mock_cls:
            with patch("app.infrastructure.messaging.kafka_producer.settings") as mock_settings:
                mock_settings.KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
                producer = KafkaEventProducer()
                await producer.start()

                mock_cls.assert_called_once_with(
                    bootstrap_servers="kafka:9092",
                    client_id="agent-platform",
                    value_serializer=mock_cls.call_args[1]["value_serializer"],
                )
                mock_producer.start.assert_awaited_once()

    async def test_stop_calls_producer_stop(self, event_producer, mock_producer):
        await event_producer.stop()
        mock_producer.stop.assert_awaited_once()

    async def test_stop_when_not_started(self):
        producer = KafkaEventProducer()
        # Should not raise
        await producer.stop()


class TestPublishEvent:
    """Test publish_event method."""

    async def test_publish_event_success(self, event_producer, mock_producer):
        event = SampleEvent(aggregate_id="agg-123", data={"key": "value"})

        await event_producer.publish_event(event)

        mock_producer.send_and_wait.assert_awaited_once()
        call_args = mock_producer.send_and_wait.await_args

        # Verify topic
        assert call_args[0][0] == "SampleEvent"

        # Verify message structure
        message = call_args[0][1]
        assert message["event_id"] == event.event_id
        assert message["event_type"] == "SampleEvent"
        assert message["aggregate_id"] == "agg-123"
        assert message["data"] == {"key": "value"}
        assert "occurred_at" in message

        # Verify partition key
        assert call_args.kwargs["key"] == b"agg-123"

    async def test_publish_event_custom_topic(self, event_producer, mock_producer):
        event = SampleEvent(aggregate_id="agg-456")

        await event_producer.publish_event(event, topic="custom-topic")

        mock_producer.send_and_wait.assert_awaited_once()
        assert mock_producer.send_and_wait.await_args[0][0] == "custom-topic"

    async def test_publish_event_not_started(self):
        producer = KafkaEventProducer()
        event = SampleEvent(aggregate_id="agg-123")

        with pytest.raises(RuntimeError, match="Kafka producer not started"):
            await producer.publish_event(event)


class TestPublishEvents:
    """Test publish_events method."""

    async def test_publish_multiple_events(self, event_producer, mock_producer):
        events = [
            SampleEvent(aggregate_id="agg-1", data={"seq": 1}),
            SampleEvent(aggregate_id="agg-1", data={"seq": 2}),
            SampleEvent(aggregate_id="agg-2", data={"seq": 3}),
        ]

        await event_producer.publish_events(events)

        assert mock_producer.send_and_wait.await_count == 3

    async def test_publish_events_empty_list(self, event_producer, mock_producer):
        await event_producer.publish_events([])
        mock_producer.send_and_wait.assert_not_awaited()

    async def test_publish_events_custom_topic(self, event_producer, mock_producer):
        events = [
            SampleEvent(aggregate_id="agg-1"),
            SampleEvent(aggregate_id="agg-2"),
        ]

        await event_producer.publish_events(events, topic="bulk-topic")

        assert mock_producer.send_and_wait.await_count == 2
        for call in mock_producer.send_and_wait.await_args_list:
            assert call[0][0] == "bulk-topic"
