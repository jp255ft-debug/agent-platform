"""Unit tests for reconciliation scripts.

Tests the matching logic, report generation, and data types
for all three reconciliation types.

Usage:
    python -m pytest scripts/tests/test_reconciliation.py -v
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.reconciliation.reconcile_payments import (
    BlockchainPaymentReader,
    EventStoreReader,
    PaymentMatcher,
    OnChainPayment,
    OffChainBillingSession,
    ReconciliationReport,
    generate_report_summary,
    generate_report_json,
)
from scripts.reconciliation.reconcile_delegations import (
    BlockchainDelegationReader,
    DelegationEventStoreReader,
    DelegationMatcher,
    OnChainDelegation,
    OffChainDelegationEvent,
)
from scripts.reconciliation.reconcile_state_channels import (
    BlockchainChannelReader,
    ChannelEventStoreReader,
    ChannelMatcher,
    OnChainChannelEvent,
    OffChainChannelEvent,
)


# =============================================================================
# Payment Reconciliation Tests
# =============================================================================


class TestPaymentMatcher:
    """Tests for the payment matching engine."""

    def test_exact_match(self):
        """Test that exact matches are correctly identified."""
        on_chain = [
            OnChainPayment(
                tx_hash="0xabc",
                sender="0x111",
                recipient="0x222",
                amount=1000,
                nonce=1,
                block_number=100,
                block_timestamp=1000000,
                log_index=0,
            )
        ]
        off_chain = [
            OffChainBillingSession(
                session_id="session_1",
                agent_id="agent_1",
                tx_hash="0xabc",
                amount=1000,
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
        ]

        matcher = PaymentMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 1
        assert report.on_chain_only == 0
        assert report.off_chain_only == 0
        assert report.amount_mismatches == 0
        assert report.is_healthy

    def test_amount_mismatch(self):
        """Test that amount mismatches are detected."""
        on_chain = [
            OnChainPayment(
                tx_hash="0xabc",
                sender="0x111",
                recipient="0x222",
                amount=1000,
                nonce=1,
                block_number=100,
                block_timestamp=1000000,
                log_index=0,
            )
        ]
        off_chain = [
            OffChainBillingSession(
                session_id="session_1",
                agent_id="agent_1",
                tx_hash="0xabc",
                amount=2000,
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
        ]

        matcher = PaymentMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 0
        assert report.amount_mismatches == 1
        assert report.total_discrepancy == 1000

    def test_on_chain_only(self):
        """Test that on-chain-only records are detected."""
        on_chain = [
            OnChainPayment(
                tx_hash="0xabc",
                sender="0x111",
                recipient="0x222",
                amount=1000,
                nonce=1,
                block_number=100,
                block_timestamp=1000000,
                log_index=0,
            )
        ]
        off_chain = []

        matcher = PaymentMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 0
        assert report.on_chain_only == 1
        assert report.off_chain_only == 0

    def test_off_chain_only(self):
        """Test that off-chain-only records are detected."""
        on_chain = []
        off_chain = [
            OffChainBillingSession(
                session_id="session_1",
                agent_id="agent_1",
                tx_hash="0xabc",
                amount=1000,
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
        ]

        matcher = PaymentMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 0
        assert report.on_chain_only == 0
        assert report.off_chain_only == 1

    def test_empty_both(self):
        """Test with no records on either side."""
        matcher = PaymentMatcher()
        report = matcher.match([], [])

        assert report.matched == 0
        assert report.total_on_chain == 0
        assert report.total_off_chain == 0
        assert report.is_healthy

    def test_discrepancy_rate_calculation(self):
        """Test discrepancy rate calculation."""
        on_chain = [
            OnChainPayment(
                tx_hash=f"0x{i}",
                sender="0x111",
                recipient="0x222",
                amount=1000,
                nonce=i,
                block_number=100 + i,
                block_timestamp=1000000 + i,
                log_index=i,
            )
            for i in range(10)
        ]
        off_chain = [
            OffChainBillingSession(
                session_id=f"session_{i}",
                agent_id=f"agent_{i}",
                tx_hash=f"0x{i}",
                amount=1000,
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
            for i in range(8)
        ]

        matcher = PaymentMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 8
        assert report.on_chain_only == 2
        assert report.discrepancy_rate == 2 / 10  # 20%


class TestPaymentReportGeneration:
    """Tests for payment report generation."""

    def test_report_summary_format(self):
        """Test that report summary is properly formatted."""
        report = ReconciliationReport(
            run_id="test_001",
            timestamp=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=24),
            window_end=datetime.now(timezone.utc),
            total_on_chain=10,
            total_off_chain=10,
            matched=10,
        )
        summary = generate_report_summary(report)
        assert "RECONCILIATION REPORT" in summary
        assert "test_001" in summary
        assert "✅ HEALTHY" in summary

    def test_report_json_format(self):
        """Test that JSON report is valid."""
        report = ReconciliationReport(
            run_id="test_001",
            timestamp=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=24),
            window_end=datetime.now(timezone.utc),
            total_on_chain=10,
            total_off_chain=10,
            matched=10,
        )
        json_str = generate_report_json(report)
        data = json.loads(json_str)
        assert data["run_id"] == "test_001"
        assert data["matched"] == 10
        assert data["is_healthy"] == True


# =============================================================================
# Delegation Reconciliation Tests
# =============================================================================


class TestDelegationMatcher:
    """Tests for the delegation matching engine."""

    def test_exact_match(self):
        """Test that exact delegation matches are identified."""
        on_chain = [
            OnChainDelegation(
                agent="0x111",
                delegate="0x222",
                expires_at=9999999999,
                active=True,
                block_number=100,
                tx_hash="0xabc",
            )
        ]
        off_chain = [
            OffChainDelegationEvent(
                event_id="evt_1",
                agent_id="0x111",
                event_type="AgentDelegated",
                delegate="0x222",
                expires_at=9999999999,
                occurred_at=datetime.now(timezone.utc),
            )
        ]

        matcher = DelegationMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 1
        assert report.state_mismatches == 0

    def test_state_mismatch(self):
        """Test that state mismatches are detected."""
        on_chain = [
            OnChainDelegation(
                agent="0x111",
                delegate="0x222",
                expires_at=9999999999,
                active=False,
                block_number=100,
                tx_hash="0xabc",
            )
        ]
        off_chain = [
            OffChainDelegationEvent(
                event_id="evt_1",
                agent_id="0x111",
                event_type="AgentDelegated",
                delegate="0x222",
                expires_at=9999999999,
                occurred_at=datetime.now(timezone.utc),
            )
        ]

        matcher = DelegationMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.state_mismatches == 1
        assert report.matched == 0


# =============================================================================
# State Channel Reconciliation Tests
# =============================================================================


class TestChannelMatcher:
    """Tests for the state channel matching engine."""

    def test_exact_match(self):
        """Test that exact channel matches are identified."""
        on_chain = [
            OnChainChannelEvent(
                channel_id="0xchannel_1",
                event_type="ChannelCreated",
                participant1="0x111",
                participant2="0x222",
                balance1=1000,
                balance2=500,
                block_number=100,
                tx_hash="0xabc",
            )
        ]
        off_chain = [
            OffChainChannelEvent(
                event_id="evt_1",
                channel_id="0xchannel_1",
                event_type="StateChannelCreated",
                data={},
                occurred_at=datetime.now(timezone.utc),
            )
        ]

        matcher = ChannelMatcher()
        report = matcher.match(on_chain, off_chain)

        assert report.matched == 1
        assert report.state_mismatches == 0

    def test_pending_disputes(self):
        """Test that pending disputes are counted."""
        on_chain = [
            OnChainChannelEvent(
                channel_id="0xchannel_1",
                event_type="DisputeRaised",
                participant1="0x111",
                participant2=None,
                balance1=None,
                balance2=None,
                block_number=100,
                tx_hash="0xabc",
            )
        ]

        matcher = ChannelMatcher()
        report = matcher.match(on_chain, [])

        assert report.pending_disputes == 1


# =============================================================================
# Blockchain Reader Tests (Mocked)
# =============================================================================


class TestBlockchainPaymentReader:
    """Tests for the blockchain payment reader with mocked Web3."""

    @pytest.mark.asyncio
    async def test_no_contract_address(self):
        """Test behavior when no contract address is configured."""
        reader = BlockchainPaymentReader(
            rpc_url="https://test.url", contract_address=None
        )
        events = await reader.get_events(0, 100)
        assert events == []


class TestEventStoreReader:
    """Tests for the event store reader with mocked database."""

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """Test behavior when no events are found."""
        reader = EventStoreReader(database_url="sqlite+aiosqlite:///:memory:")
        sessions = await reader.get_billing_sessions(datetime.now(timezone.utc))
        assert sessions == []
        await reader.close()
