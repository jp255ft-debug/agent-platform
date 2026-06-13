"""Payment reconciliation: on-chain PaymentVerifier events vs. off-chain event store.

This script:
1. Fetches PaymentVerified events from the blockchain (last N hours)
2. Queries the event store for corresponding billing sessions
3. Matches transactions and detects discrepancies
4. Generates a reconciliation report
5. Sends alerts if discrepancy rate exceeds threshold

Usage:
    python -m scripts.reconciliation.reconcile_payments
    python -m scripts.reconciliation.reconcile_payments --hours 48 --alert
"""

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.types import EventData
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from scripts.reconciliation.config import config

logger = logging.getLogger(__name__)

# =============================================================================
# Data Types
# =============================================================================


@dataclass
class OnChainPayment:
    """A payment event recorded on-chain."""

    tx_hash: str
    sender: str
    recipient: str
    amount: int
    nonce: int
    block_number: int
    block_timestamp: int
    log_index: int


@dataclass
class OffChainBillingSession:
    """A billing session recorded in the event store."""

    session_id: str
    agent_id: str
    tx_hash: Optional[str]
    amount: int
    status: str  # started, completed, settled, failed
    created_at: datetime


@dataclass
class ReconciliationMatch:
    """A matched or unmatched payment record."""

    on_chain: Optional[OnChainPayment]
    off_chain: Optional[OffChainBillingSession]
    status: str  # matched, on_chain_only, off_chain_only, amount_mismatch
    discrepancy: int = 0  # Difference in amount (wei)


@dataclass
class ReconciliationReport:
    """Full reconciliation report."""

    run_id: str
    timestamp: datetime
    window_start: datetime
    window_end: datetime

    total_on_chain: int = 0
    total_off_chain: int = 0
    matched: int = 0
    on_chain_only: int = 0
    off_chain_only: int = 0
    amount_mismatches: int = 0

    total_on_chain_amount: int = 0
    total_off_chain_amount: int = 0
    total_discrepancy: int = 0

    matches: List[ReconciliationMatch] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def discrepancy_rate(self) -> float:
        """Rate of discrepancies relative to total transactions."""
        total = self.matched + self.on_chain_only + self.off_chain_only
        if total == 0:
            return 0.0
        return (self.on_chain_only + self.off_chain_only + self.amount_mismatches) / total

    @property
    def is_healthy(self) -> bool:
        """Whether the system is within acceptable discrepancy thresholds."""
        return self.discrepancy_rate <= config.max_discrepancy_rate


# =============================================================================
# Blockchain Client
# =============================================================================


class BlockchainPaymentReader:
    """Reads PaymentVerified events from the PaymentVerifier contract."""

    # PaymentVerified(address indexed sender, address indexed recipient, uint256 amount, uint256 nonce)
    PAYMENT_VERIFIED_EVENT_SIG = "PaymentVerified(address,address,uint256,uint256)"

    def __init__(self, rpc_url: str, contract_address: Optional[str] = None):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._contract_address = (
            Web3.to_checksum_address(contract_address) if contract_address else None
        )

        # Build event signature hash
        self._event_topic = Web3.keccak(text=self.PAYMENT_VERIFIED_EVENT_SIG).hex()

    async def get_events(
        self, from_block: int, to_block: int
    ) -> List[OnChainPayment]:
        """Fetch PaymentVerified events in a block range."""
        if not self._contract_address:
            logger.warning("No PaymentVerifier contract address configured")
            return []

        try:
            logs = self._w3.eth.get_logs(
                {
                    "address": self._contract_address,
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "topics": [self._event_topic],
                }
            )
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            return []

        payments = []
        for log in logs:
            try:
                # Decode event data
                # topics[1] = indexed sender, topics[2] = indexed recipient
                # data = abi.encode(amount, nonce)
                sender = Web3.to_checksum_address("0x" + log["topics"][1].hex()[-40:])
                recipient = Web3.to_checksum_address("0x" + log["topics"][2].hex()[-40:])

                # Decode non-indexed params: amount (uint256), nonce (uint256)
                decoded = self._w3.codec.decode(
                    ["uint256", "uint256"], log["data"]
                )
                amount = decoded[0]
                nonce = decoded[1]

                # Get block timestamp
                block = self._w3.eth.get_block(log["blockNumber"])

                payments.append(
                    OnChainPayment(
                        tx_hash=log["transactionHash"].hex(),
                        sender=sender,
                        recipient=recipient,
                        amount=amount,
                        nonce=nonce,
                        block_number=log["blockNumber"],
                        block_timestamp=block["timestamp"],
                        log_index=log["logIndex"],
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to decode log entry: {e}")
                continue

        return payments

    async def get_current_block(self) -> int:
        """Get the latest block number."""
        return self._w3.eth.block_number

    async def get_block_timestamp(self, block_number: int) -> int:
        """Get the timestamp of a block."""
        block = self._w3.eth.get_block(block_number)
        return block["timestamp"]


# =============================================================================
# Event Store Client
# =============================================================================


class EventStoreReader:
    """Reads billing session events from the PostgreSQL event store."""

    def __init__(self, database_url: str):
        self._engine = create_async_engine(database_url)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession
        )

    async def get_billing_sessions(
        self, since: datetime
    ) -> List[OffChainBillingSession]:
        """Fetch billing sessions from the event store since a given timestamp."""
        async with self._session_factory() as session:
            # Query billing session events
            query = text("""
                SELECT
                    e.event_id,
                    e.aggregate_id,
                    e.event_type,
                    e.data,
                    e.occurred_at
                FROM events e
                WHERE e.event_type IN (
                    'BillingSessionStarted',
                    'BillingSessionCompleted',
                    'BillingSessionSettled',
                    'BillingSessionClosed'
                )
                AND e.occurred_at >= :since
                ORDER BY e.occurred_at ASC
            """)

            result = await session.execute(query, {"since": since})
            rows = result.fetchall()

            # Group by aggregate_id to build session state
            sessions: Dict[str, OffChainBillingSession] = {}
            for row in rows:
                data = row.data if isinstance(row.data, dict) else json.loads(row.data)
                aggregate_id = row.aggregate_id

                if row.event_type == "BillingSessionStarted":
                    sessions[aggregate_id] = OffChainBillingSession(
                        session_id=aggregate_id,
                        agent_id=data.get("agent_id", ""),
                        tx_hash=data.get("tx_hash"),
                        amount=data.get("amount", 0),
                        status="started",
                        created_at=row.occurred_at,
                    )
                elif row.event_type in ("BillingSessionCompleted", "BillingSessionSettled"):
                    if aggregate_id in sessions:
                        sessions[aggregate_id].status = "completed"
                        if data.get("tx_hash"):
                            sessions[aggregate_id].tx_hash = data["tx_hash"]
                elif row.event_type == "BillingSessionClosed":
                    if aggregate_id in sessions:
                        sessions[aggregate_id].status = "settled"

            return list(sessions.values())

    async def close(self):
        """Close the database connection."""
        await self._engine.dispose()


# =============================================================================
# Alerting
# =============================================================================


class AlertSender:
    """Sends alerts via webhook when discrepancies are detected."""

    def __init__(self, webhook_url: Optional[str] = None):
        self._webhook_url = webhook_url

    async def send_alert(self, report: ReconciliationReport):
        """Send an alert if discrepancy rate exceeds threshold."""
        if not self._webhook_url:
            logger.info("No webhook configured, skipping alert")
            return

        if report.is_healthy:
            logger.info(
                f"System healthy: {report.discrepancy_rate:.4%} discrepancy rate "
                f"(threshold: {config.max_discrepancy_rate:.4%})"
            )
            return

        message = (
            f"🚨 *Reconciliation Alert*\n"
            f"Discrepancy rate: {report.discrepancy_rate:.4%}\n"
            f"Threshold: {config.max_discrepancy_rate:.4%}\n"
            f"On-chain only: {report.on_chain_only}\n"
            f"Off-chain only: {report.off_chain_only}\n"
            f"Amount mismatches: {report.amount_mismatches}\n"
            f"Total discrepancy: {report.total_discrepancy} wei\n"
            f"Window: {report.window_start} to {report.window_end}"
        )

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                await client.post(
                    self._webhook_url,
                    json={"text": message},
                    timeout=10,
                )
            logger.info("Alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")


# =============================================================================
# Matching Engine
# =============================================================================


class PaymentMatcher:
    """Matches on-chain payments with off-chain billing sessions."""

    def match(
        self,
        on_chain_payments: List[OnChainPayment],
        off_chain_sessions: List[OffChainBillingSession],
    ) -> ReconciliationReport:
        """Match on-chain and off-chain records and produce a report."""
        report = ReconciliationReport(
            run_id=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=config.reconciliation_window_hours),
            window_end=datetime.now(timezone.utc),
        )

        report.total_on_chain = len(on_chain_payments)
        report.total_off_chain = len(off_chain_sessions)

        # Build lookup by tx_hash for off-chain sessions
        off_chain_by_tx: Dict[str, OffChainBillingSession] = {}
        for session in off_chain_sessions:
            if session.tx_hash:
                off_chain_by_tx[session.tx_hash.lower()] = session

        # Track matched off-chain sessions
        matched_off_chain: set = set()

        # Match on-chain payments to off-chain sessions
        for payment in on_chain_payments:
            tx_hash_lower = payment.tx_hash.lower()
            if tx_hash_lower in off_chain_by_tx:
                session = off_chain_by_tx[tx_hash_lower]
                matched_off_chain.add(tx_hash_lower)

                if payment.amount == session.amount:
                    report.matched += 1
                    report.matches.append(
                        ReconciliationMatch(
                            on_chain=payment,
                            off_chain=session,
                            status="matched",
                        )
                    )
                else:
                    report.amount_mismatches += 1
                    discrepancy = abs(payment.amount - session.amount)
                    report.total_discrepancy += discrepancy
                    report.matches.append(
                        ReconciliationMatch(
                            on_chain=payment,
                            off_chain=session,
                            status="amount_mismatch",
                            discrepancy=discrepancy,
                        )
                    )
            else:
                report.on_chain_only += 1
                report.total_discrepancy += payment.amount
                report.matches.append(
                    ReconciliationMatch(
                        on_chain=payment,
                        off_chain=None,
                        status="on_chain_only",
                        discrepancy=payment.amount,
                    )
                )

        # Find off-chain sessions not matched to any on-chain payment
        for session in off_chain_sessions:
            tx_key = session.tx_hash.lower() if session.tx_hash else ""
            if tx_key not in matched_off_chain:
                report.off_chain_only += 1
                report.total_discrepancy += session.amount
                report.matches.append(
                    ReconciliationMatch(
                        on_chain=None,
                        off_chain=session,
                        status="off_chain_only",
                        discrepancy=session.amount,
                    )
                )

        report.total_on_chain_amount = sum(p.amount for p in on_chain_payments)
        report.total_off_chain_amount = sum(s.amount for s in off_chain_sessions)

        return report


# =============================================================================
# Report Generation
# =============================================================================


def generate_report_json(report: ReconciliationReport) -> str:
    """Generate a JSON report file."""
    return json.dumps(asdict(report), default=str, indent=2)


def generate_report_summary(report: ReconciliationReport) -> str:
    """Generate a human-readable summary."""
    lines = [
        "=" * 60,
        f"RECONCILIATION REPORT - {report.run_id}",
        f"Timestamp: {report.timestamp.isoformat()}",
        f"Window: {report.window_start.isoformat()} to {report.window_end.isoformat()}",
        "=" * 60,
        "",
        f"On-chain payments:    {report.total_on_chain}",
        f"Off-chain sessions:   {report.total_off_chain}",
        "",
        f"✅ Matched:           {report.matched}",
        f"⚠️  On-chain only:    {report.on_chain_only}",
        f"⚠️  Off-chain only:   {report.off_chain_only}",
        f"❌ Amount mismatches: {report.amount_mismatches}",
        "",
        f"On-chain total:       {report.total_on_chain_amount} wei",
        f"Off-chain total:      {report.total_off_chain_amount} wei",
        f"Total discrepancy:    {report.total_discrepancy} wei",
        "",
        f"Discrepancy rate:     {report.discrepancy_rate:.4%}",
        f"Threshold:            {config.max_discrepancy_rate:.4%}",
        f"Status:               {'✅ HEALTHY' if report.is_healthy else '❌ UNHEALTHY'}",
        "",
    ]

    if report.errors:
        lines.append("Errors:")
        for err in report.errors:
            lines.append(f"  - {err}")

    if report.matches:
        # Show unmatched records
        unmatched = [m for m in report.matches if m.status != "matched"]
        if unmatched:
            lines.append("")
            lines.append("Unmatched Records:")
            lines.append("-" * 40)
            for m in unmatched[:20]:  # Show first 20
                if m.status == "on_chain_only":
                    lines.append(
                        f"  [ON-CHAIN ONLY] tx={m.on_chain.tx_hash[:20]}... "
                        f"amount={m.on_chain.amount} sender={m.on_chain.sender[:10]}..."
                    )
                elif m.status == "off_chain_only":
                    lines.append(
                        f"  [OFF-CHAIN ONLY] session={m.off_chain.session_id[:20]}... "
                        f"amount={m.off_chain.amount} agent={m.off_chain.agent_id[:10]}..."
                    )
                elif m.status == "amount_mismatch":
                    lines.append(
                        f"  [AMOUNT MISMATCH] tx={m.on_chain.tx_hash[:20]}... "
                        f"on_chain={m.on_chain.amount} off_chain={m.off_chain.amount} "
                        f"diff={m.discrepancy}"
                    )

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# =============================================================================
# Main Reconciliation Flow
# =============================================================================


async def run_reconciliation(
    hours: int = 24,
    alert: bool = False,
    output_dir: Optional[str] = None,
) -> ReconciliationReport:
    """Run the full payment reconciliation flow.

    Args:
        hours: Number of hours to look back
        alert: Whether to send alerts on discrepancies
        output_dir: Directory to save report files

    Returns:
        ReconciliationReport with all findings
    """
    logger.info(f"Starting payment reconciliation (window: {hours}h)")

    # Initialize clients
    blockchain = BlockchainPaymentReader(
        rpc_url=config.rpc_url,
        contract_address=config.payment_verifier_address,
    )
    event_store = EventStoreReader(database_url=config.database_url)
    matcher = PaymentMatcher()
    alert_sender = AlertSender(webhook_url=config.alert_webhook if alert else None)

    try:
        # Calculate block range
        current_block = await blockchain.get_current_block()
        current_timestamp = await blockchain.get_block_timestamp(current_block)
        window_start_ts = current_timestamp - (hours * 3600)

        # Estimate block at window start (assuming ~2s block time on Base)
        blocks_in_window = hours * 3600 // 2
        from_block = max(0, current_block - blocks_in_window)

        logger.info(
            f"Scanning blocks {from_block} to {current_block} "
            f"(~{hours}h window)"
        )

        # Fetch on-chain events
        on_chain_payments = await blockchain.get_events(from_block, current_block)
        logger.info(f"Found {len(on_chain_payments)} on-chain payment events")

        # Fetch off-chain events
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        off_chain_sessions = await event_store.get_billing_sessions(since)
        logger.info(f"Found {len(off_chain_sessions)} off-chain billing sessions")

        # Match
        report = matcher.match(on_chain_payments, off_chain_sessions)

        # Generate outputs
        summary = generate_report_summary(report)
        print(summary)

        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Save JSON report
            json_path = output_path / f"reconciliation_{report.run_id}.json"
            json_path.write_text(generate_report_json(report))
            logger.info(f"Report saved to {json_path}")

            # Save summary
            summary_path = output_path / f"reconciliation_{report.run_id}.txt"
            summary_path.write_text(summary)
            logger.info(f"Summary saved to {summary_path}")

        # Send alert if needed
        if alert:
            await alert_sender.send_alert(report)

        return report

    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        report = ReconciliationReport(
            run_id="error",
            timestamp=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=hours),
            window_end=datetime.now(timezone.utc),
            errors=[str(e)],
        )
        return report
    finally:
        await event_store.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reconcile on-chain payments with off-chain event store"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=config.reconciliation_window_hours,
        help=f"Lookback window in hours (default: {config.reconciliation_window_hours})",
    )
    parser.add_argument(
        "--alert",
        action="store_true",
        help="Send alerts on discrepancies",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory to save reports (default: reports/)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    report = asyncio.run(
        run_reconciliation(
            hours=args.hours,
            alert=args.alert,
            output_dir=args.output_dir,
        )
    )

    if not report.is_healthy:
        exit(1)


if __name__ == "__main__":
    main()
