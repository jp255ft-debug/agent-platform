"""Unit tests for AgentAggregate."""
import pytest

from app.domain.aggregates.agent import AgentAggregate
from app.domain.events.agent_events import (
    AgentRegistered,
    AgentDelegated,
    AgentDelegationRevoked,
    AgentReputationUpdated,
)


class TestAgentRegister:
    def test_register_creates_agent(self):
        agent = AgentAggregate.register(
            agent_id="agent-1",
            owner_address="0x1234",
        )
        assert agent.agent_id == "agent-1"
        assert agent.owner_address == "0x1234"
        assert agent.delegation_address is None
        assert agent.delegation_active is False
        assert agent.reputation_score == 100

    def test_register_with_delegation_address(self):
        agent = AgentAggregate.register(
            agent_id="agent-1",
            owner_address="0x1234",
            delegation_address="0xdeleg",
        )
        assert agent.delegation_address == "0xdeleg"

    def test_register_emits_agent_registered_event(self):
        agent = AgentAggregate.register(
            agent_id="agent-1",
            owner_address="0x1234",
        )
        changes = agent.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], AgentRegistered)
        assert changes[0].data["owner_address"] == "0x1234"


class TestAgentDelegate:
    def test_delegate_sets_delegation_active(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.clear_changes()
        agent.delegate(delegate_address="0xdeleg", expires_at="2027-01-01")
        assert agent.delegation_address == "0xdeleg"
        assert agent.delegation_active is True

    def test_delegate_emits_agent_delegated_event(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.clear_changes()
        agent.delegate(delegate_address="0xdeleg", expires_at="2027-01-01")
        changes = agent.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], AgentDelegated)
        assert changes[0].data["delegate_address"] == "0xdeleg"
        assert changes[0].data["expires_at"] == "2027-01-01"


class TestAgentRevokeDelegation:
    def test_revoke_delegation_sets_active_false(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.delegate("0xdeleg", "2027-01-01")
        agent.clear_changes()
        agent.revoke_delegation()
        assert agent.delegation_active is False

    def test_revoke_delegation_emits_revoked_event(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.clear_changes()
        agent.revoke_delegation()
        changes = agent.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], AgentDelegationRevoked)


class TestAgentUpdateReputation:
    def test_update_reputation_changes_score(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.clear_changes()
        agent.update_reputation(new_score=85, reason="good_performance")
        assert agent.reputation_score == 85

    def test_update_reputation_emits_event(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.clear_changes()
        agent.update_reputation(new_score=50, reason="violation")
        changes = agent.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], AgentReputationUpdated)
        assert changes[0].data["new_score"] == 50
        assert changes[0].data["reason"] == "violation"


class TestAgentEventSourcing:
    def test_rebuild_from_events(self):
        agent = AgentAggregate(agent_id="agent-1")
        event1 = AgentRegistered(
            "agent-1", "0x1234", None,
        )
        event2 = AgentDelegated(
            "agent-1", "0xdeleg", "2027-01-01",
        )
        event3 = AgentReputationUpdated(
            "agent-1", 75, "penalty",
        )
        agent._apply(event1)
        agent._apply(event2)
        agent._apply(event3)
        assert agent.owner_address == "0x1234"
        assert agent.delegation_address == "0xdeleg"
        assert agent.delegation_active is True
        assert agent.reputation_score == 75
        assert agent.version == 3

    def test_get_changes_returns_copy(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        changes = agent.get_changes()
        assert len(changes) == 1
        changes.clear()
        assert len(agent.get_changes()) == 1

    def test_clear_changes_empties_list(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        agent.clear_changes()
        assert len(agent.get_changes()) == 0

    def test_version_increments(self):
        agent = AgentAggregate.register("agent-1", "0x1234")
        assert agent.version == 1
        agent.delegate("0xdeleg", "2027-01-01")
        assert agent.version == 2
        agent.revoke_delegation()
        assert agent.version == 3
