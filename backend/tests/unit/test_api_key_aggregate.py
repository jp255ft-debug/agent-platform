"""Unit tests for APIKeyAggregate."""
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.aggregates.api_key import APIKeyAggregate
from app.domain.events.api_key_events import (
    APIKeyCreated,
    APIKeyRevoked,
    APIKeyExpired,
    APIKeyUsed,
)


class TestAPIKeyAggregateCreate:
    """Tests for APIKeyAggregate.create() factory."""

    def test_create_returns_aggregate_with_one_key(self):
        aggregate = APIKeyAggregate.create(
            agent_id="agent-123",
            key_id="key-001",
            key_hash="hashed_value",
            expires_in_days=90,
        )
        assert aggregate.agent_id == "agent-123"
        assert len(aggregate.keys) == 1
        assert aggregate.keys[0].key_id == "key-001"
        assert aggregate.keys[0].key_hash == "hashed_value"
        assert not aggregate.keys[0].revoked
        assert not aggregate.keys[0].expired

    def test_create_sets_expiration_correctly(self):
        aggregate = APIKeyAggregate.create(
            agent_id="agent-123",
            key_id="key-001",
            key_hash="hash",
            expires_in_days=30,
        )
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        assert aggregate.keys[0].expires_at.date() == expected.date()

    def test_create_generates_api_key_created_event(self):
        aggregate = APIKeyAggregate.create(
            agent_id="agent-123",
            key_id="key-001",
            key_hash="hash",
        )
        changes = aggregate.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], APIKeyCreated)
        assert changes[0].aggregate_id == "agent-123"
        assert changes[0].data["key_id"] == "key-001"

    def test_create_default_expires_in_90_days(self):
        aggregate = APIKeyAggregate.create(
            agent_id="agent-123",
            key_id="key-001",
            key_hash="hash",
        )
        expected = datetime.now(timezone.utc) + timedelta(days=90)
        assert aggregate.keys[0].expires_at.date() == expected.date()


class TestAPIKeyAggregateRevoke:
    """Tests for APIKeyAggregate.revoke_key()."""

    def test_revoke_key_marks_key_as_revoked(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.revoke_key("key-001", reason="compromised")
        assert aggregate.keys[0].revoked is True
        assert aggregate.keys[0].revoked_at is not None

    def test_revoke_key_generates_api_key_revoked_event(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.get_changes()  # clear create event
        aggregate.revoke_key("key-001", reason="compromised")
        changes = aggregate.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], APIKeyRevoked)
        assert changes[0].data["reason"] == "compromised"

    def test_revoke_key_default_reason_is_manual(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.get_changes()
        aggregate.revoke_key("key-001")
        changes = aggregate.get_changes()
        assert changes[0].data["reason"] == "manual"


class TestAPIKeyAggregateRotate:
    """Tests for APIKeyAggregate.rotate_key()."""

    def test_rotate_key_revokes_old_and_creates_new(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_old")
        aggregate.get_changes()
        aggregate.rotate_key("key-001", "key-002", "hash_new", expires_in_days=90)
        assert aggregate.keys[0].revoked is True  # old key revoked
        assert aggregate.keys[1].key_id == "key-002"
        assert aggregate.keys[1].key_hash == "hash_new"
        assert not aggregate.keys[1].revoked

    def test_rotate_key_generates_two_events(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_old")
        aggregate.get_changes()
        aggregate.rotate_key("key-001", "key-002", "hash_new")
        changes = aggregate.get_changes()
        assert len(changes) == 2
        assert isinstance(changes[0], APIKeyRevoked)
        assert isinstance(changes[1], APIKeyCreated)
        assert changes[0].data["reason"] == "rotation"


class TestAPIKeyAggregateExpire:
    """Tests for APIKeyAggregate.expire_keys()."""

    def test_expire_keys_marks_expired_keys(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        # Manually set expiration in the past
        aggregate.keys[0].expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        aggregate.get_changes()
        aggregate.expire_keys()
        assert aggregate.keys[0].expired is True

    def test_expire_keys_does_not_affect_valid_keys(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.get_changes()
        aggregate.expire_keys()
        assert not aggregate.keys[0].expired

    def test_expire_keys_generates_api_key_expired_event(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.keys[0].expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        aggregate.get_changes()
        aggregate.expire_keys()
        changes = aggregate.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], APIKeyExpired)


class TestAPIKeyAggregateValidation:
    """Tests for APIKeyAggregate.is_valid()."""

    def test_valid_key_returns_true(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_valid")
        assert aggregate.is_valid("hash_valid") is True

    def test_revoked_key_returns_false(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_valid")
        aggregate.revoke_key("key-001")
        assert aggregate.is_valid("hash_valid") is False

    def test_expired_key_returns_false(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_valid")
        aggregate.keys[0].expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        aggregate.expire_keys()
        assert aggregate.is_valid("hash_valid") is False

    def test_unknown_hash_returns_false(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_valid")
        assert aggregate.is_valid("unknown_hash") is False

    def test_multiple_keys_only_valid_one_returns_true(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_old")
        aggregate.get_changes()
        aggregate.rotate_key("key-001", "key-002", "hash_new")
        assert aggregate.is_valid("hash_new") is True
        assert aggregate.is_valid("hash_old") is False


class TestAPIKeyAggregateActiveKeys:
    """Tests for APIKeyAggregate.active_keys()."""

    def test_active_keys_returns_only_valid_keys(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash_1")
        aggregate.get_changes()
        aggregate.rotate_key("key-001", "key-002", "hash_2")
        active = aggregate.active_keys()
        assert len(active) == 1
        assert active[0].key_id == "key-002"

    def test_active_keys_empty_when_all_revoked(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.revoke_key("key-001")
        assert len(aggregate.active_keys()) == 0


class TestAPIKeyAggregateRecordUsage:
    """Tests for APIKeyAggregate.record_usage()."""

    def test_record_usage_adds_event(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.get_changes()
        aggregate.record_usage("key-001", ip_address="192.168.1.1")
        changes = aggregate.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], APIKeyUsed)
        assert changes[0].data["key_id"] == "key-001"
        assert changes[0].data["ip_address"] == "192.168.1.1"

    def test_record_usage_default_ip(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        aggregate.get_changes()
        aggregate.record_usage("key-001")
        changes = aggregate.get_changes()
        assert changes[0].data["ip_address"] == "unknown"


class TestAPIKeyAggregateEventSourcing:
    """Tests for event sourcing rebuild."""

    def test_rebuild_from_events(self):
        # Simulate loading from event store
        aggregate = APIKeyAggregate(agent_id="agent-123")
        event1 = APIKeyCreated(
            aggregate_id="agent-123",
            data={
                "key_id": "key-001",
                "key_hash": "hash_1",
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        event2 = APIKeyRevoked(
            aggregate_id="agent-123",
            data={"key_id": "key-001", "reason": "test", "revoked_at": datetime.now(timezone.utc).isoformat()},
        )
        aggregate._apply(event1)
        aggregate._apply(event2)
        assert len(aggregate.keys) == 1
        assert aggregate.keys[0].revoked is True
        assert aggregate.version == 2

    def test_get_changes_clears_list(self):
        aggregate = APIKeyAggregate.create("agent-123", "key-001", "hash")
        changes = aggregate.get_changes()
        assert len(changes) == 1
        assert aggregate.get_changes() == []  # empty after clear
