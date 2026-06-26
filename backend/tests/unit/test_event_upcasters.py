"""Tests for event upcasting (V1 → V2 migration for DePIN Procurement).

This test suite validates that legacy events stored in PostgreSQL JSONB
are correctly transformed by the EventUpcaster before deserialization,
ensuring backward compatibility with the new DePIN domain model.
"""
import json
import pytest
from app.infrastructure.db.upcasters import EventUpcaster


class TestResourceConsumedUpcast:
    """Tests for ResourceConsumed V1 → V2 upcasting."""

    def test_upcast_resource_consumed_v1_to_v2(self):
        """Legacy V1 event must be transformed to V2 with safe defaults.

        This simulates reading a raw JSONB payload from PostgreSQL that
        was stored before the DePIN Procurement migration.
        """
        # Arrange: Simula a leitura de um JSONB legado do banco de dados
        raw_db_payload = {
            "event_id": "uuid-1234",
            "stream_id": "billing-session-999",
            "version": 1,
            "event_type": "ResourceConsumed",
            "aggregate_id": "agent-456",
            "data": {
                "session_id": "session-abc",
                "agent_id": "agent-456",
                "amount": 1500,
                "resource_type": "llm",
            },
            "occurred_at": "2026-06-19T20:00:00Z",
        }

        # Act: Passa pelo Upcaster antes da deserialização para dataclass
        upcasted_payload = EventUpcaster.upcast(raw_db_payload)

        # Assert: Valida a transformação estrutural
        assert upcasted_payload["event_type"] == "ResourceConsumedV2"

        # Campos originais preservados
        assert upcasted_payload["data"]["resource_type"] == "llm"
        assert upcasted_payload["data"]["amount"] == 1500
        assert upcasted_payload["data"]["session_id"] == "session-abc"
        assert upcasted_payload["data"]["agent_id"] == "agent-456"

        # Novos campos de DePIN Procurement com valores seguros (zero bad-debt histórico)
        assert upcasted_payload["data"]["cost_micro_usdc"] == 0
        assert upcasted_payload["data"]["provider_id"] == "legacy_system"

        # Metadados do evento preservados
        assert upcasted_payload["event_id"] == "uuid-1234"
        assert upcasted_payload["aggregate_id"] == "agent-456"
        assert upcasted_payload["occurred_at"] == "2026-06-19T20:00:00Z"

    def test_upcast_preserves_non_consumed_events(self):
        """Events that are NOT ResourceConsumed must pass through unchanged."""
        raw_payload = {
            "event_id": "uuid-5678",
            "event_type": "AgentRegistered",
            "aggregate_id": "agent-789",
            "data": {
                "agent_id": "agent-789",
                "owner_address": "0x1234",
            },
            "occurred_at": "2026-06-19T21:00:00Z",
        }

        upcasted = EventUpcaster.upcast(raw_payload)

        # Must remain unchanged
        assert upcasted["event_type"] == "AgentRegistered"
        assert upcasted["data"]["owner_address"] == "0x1234"
        assert "cost_micro_usdc" not in upcasted["data"]
        assert "provider_id" not in upcasted["data"]

    def test_upcast_with_empty_data_field(self):
        """Edge case: ResourceConsumed with empty data must still produce safe defaults."""
        raw_payload = {
            "event_id": "uuid-9999",
            "event_type": "ResourceConsumed",
            "aggregate_id": "agent-000",
            "data": {},
            "occurred_at": "2026-06-19T22:00:00Z",
        }

        upcasted = EventUpcaster.upcast(raw_payload)

        assert upcasted["event_type"] == "ResourceConsumedV2"
        assert upcasted["data"]["cost_micro_usdc"] == 0
        assert upcasted["data"]["provider_id"] == "legacy_system"

    def test_upcast_preserves_existing_v2_fields(self):
        """If data already has V2 fields, they must be preserved (idempotency)."""
        raw_payload = {
            "event_id": "uuid-7777",
            "event_type": "ResourceConsumed",
            "aggregate_id": "agent-111",
            "data": {
                "resource_type": "GPU_COMPUTE_TFLOPS",
                "amount": 825,
                "cost_micro_usdc": 123450,  # Already has V2 field
                "provider_id": "provider-io-net",
            },
            "occurred_at": "2026-06-19T23:00:00Z",
        }

        upcasted = EventUpcaster.upcast(raw_payload)

        assert upcasted["event_type"] == "ResourceConsumedV2"
        # V2 fields must be preserved, NOT overwritten with defaults
        assert upcasted["data"]["cost_micro_usdc"] == 123450
        assert upcasted["data"]["provider_id"] == "provider-io-net"
