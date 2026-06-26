"""Event Upcasting — Schema Migration Layer for Event Sourcing.

In Event Sourcing systems, events are append-only and immutable.
When the domain model evolves (e.g., adding new fields), we cannot
modify historical events in the database. Instead, we transform them
at read time using upcasters.

This module provides the EventUpcaster that intercepts raw JSONB
payloads from PostgreSQL and upgrades them to the latest schema
version before deserialization into domain event objects.

Usage:
    raw_payload = {"event_type": "ResourceConsumed", "data": {...}}
    upcasted = EventUpcaster.upcast(raw_payload)
    # upcasted["event_type"] == "ResourceConsumedV2"
"""
from typing import Any


class EventUpcaster:
    """Transforms legacy event payloads to the latest schema version.

    Each upcast step handles a specific V{N} → V{N+1} migration.
    The pipeline is applied sequentially so events can traverse
    multiple versions (e.g., V1 → V2 → V3) if needed.

    Design decisions:
    - Stateless @staticmethod: pure transformation, no side effects
    - Operates on Dict[str, Any]: works at the JSON/serialization layer
      before any domain object is instantiated
    - Safe defaults for new fields: historical events get zero values
      to prevent bad-debt attribution to past transactions
    - Idempotent: if data already has V2 fields, they are preserved
    """

    @staticmethod
    def upcast(raw_event: dict[str, Any]) -> dict[str, Any]:
        """Apply all upcast steps to bring an event to the latest version.

        Args:
            raw_event: Raw event payload as read from the database.
                       Must contain at least "event_type" and "data" keys.

        Returns:
            Transformed event payload with the latest schema version.
        """
        event_type = raw_event.get("event_type", "")
        data = raw_event.get("data", {})

        # ──────────────────────────────────────────────────────────
        # Upcast Step: ResourceConsumed V1 → ResourceConsumedV2
        # ──────────────────────────────────────────────────────────
        # Migration: DePIN Procurement — adds cost_micro_usdc and provider_id
        if event_type == "ResourceConsumed":
            raw_event["event_type"] = "ResourceConsumedV2"

            # Preserve existing V2 fields if already present (idempotency)
            data.setdefault("cost_micro_usdc", 0)
            data.setdefault("provider_id", "legacy_system")

            raw_event["data"] = data

        # ──────────────────────────────────────────────────────────
        # Future upcast steps go here (e.g., V2 → V3)
        # ──────────────────────────────────────────────────────────

        return raw_event
