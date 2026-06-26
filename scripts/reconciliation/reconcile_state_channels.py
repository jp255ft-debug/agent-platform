"""State channel reconciliation: on-chain channel state vs. off-chain event store.

This script:
1. Fetches channel events from the blockchain (ChannelCreated, ChannelClosed, etc.)
2. Queries the event store for corresponding state channel events
3. Compares channel states and detects inconsistencies
4. Identifies channels with pending disputes or incomplete settlements

Usage:
    python -m scripts.reconciliation.reconcile_state_channels
    python -m scripts.reconciliation.reconcile_state_channels --hours 72
"""

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict

from web3 import Web3
from web3.middleware import geth_poa_middleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from scripts.reconciliation.config import config

logger = logging.getLogger(__name__)

# =============================================================================
# Data Types
# =============================================================================


@dataclass
class OnChainChannelEvent:
    """A state channel event recorded on-chain."""

    channel_id: str
    event_type: str  # ChannelCreated, ChannelClosed, DisputeRaised, ChannelSettled
    participant1: Optional[str]
    participant2: Optional[str]
    balance1: Optional[int]
    balance2: Optional[int]
    block_number: int
    tx_hash: str


@dataclass
class OffChainChannelEvent:
    """A state channel event recorded in the event store."""

    event_id: str
    channel_id: str
    event_type: str  # StateChannelCreated, StateChannelUpdate, StateChannelClosed
    data: dict
    occurred_at: datetime


@dataclass
class StateChannelReconciliationReport:
    """Report for state channel reconciliation."""

    run_id: str
    timestamp: datetime
    window_start: datetime
    window_end: datetime

    total_on_chain: int = 0
    total_off_chain: int = 0
    matched: int = 0
    on_chain_only: int = 0
    off_chain_only: int = 0
    state_mismatches: int = 0
    pending_disputes: int = 0

    on_chain_events: List[OnChainChannelEvent] = field(default_factory=list)
    off_chain_events: List[OffChainChannelEvent] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def discrepancy_rate(self) -> float:
        total = self.matched + self.on_chain_only + self.off_chain_only
        if total == 0:
            return 0.0
        return (self.on_chain_only + self.off_chain_only + self.state_mismatches) / total

    @property
    def is_healthy(self) -> bool:
        return self.discrepancy_rate <= config.max_discrepancy_rate


# =============================================================================
# Blockchain Client
# =============================================================================


class BlockchainChannelReader:
    """Reads state channel events from the blockchain."""

    # Common event signatures for state channels
    CHANNEL_CREATED_SIG = "ChannelCreated(bytes32,address,address,uint256,uint256)"
    CHANNEL_CLOSED_SIG = "ChannelClosed(bytes32,uint256,uint256)"
    DISPUTE_RAISED_SIG = "DisputeRaised(bytes32,address)"

    def __init__(self, rpc_url: str, contract_address: Optional[str] = None):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._contract_address = (
            Web3.to_checksum_address(contract_address) if contract_address else None
        )

        self._created_topic = Web3.keccak(text=self.CHANNEL_CREATED_SIG).hex()
        self._closed_topic = Web3.keccak(text=self.CHANNEL_CLOSED_SIG).hex()
        self._dispute_topic = Web3.keccak(text=self.DISPUTE_RAISED_SIG).hex()

    async def get_channel_events(
        self, from_block: int, to_block: int
    ) -> List[OnChainChannelEvent]:
        """Fetch state channel events in a block range."""
        if not self._contract_address:
            logger.warning("No state channel contract address configured")
            return []

        events = []

        try:
            # Fetch ChannelCreated events
            created_logs = self._w3.eth.get_logs({
                "address": self._contract_address,
                "fromBlock": from_block,
                "toBlock": to_block,
                "topics": [self._created_topic],
            })

            for log in created_logs:
                channel_id = "0x" + log["topics"][1].hex()
                decoded = self._w3.codec.decode(
                    ["address", "address", "uint256", "uint256"], log["data"]
                )
                events.append(OnChainChannelEvent(
                    channel_id=channel_id,
                    event_type="ChannelCreated",
                    participant1=decoded[0],
                    participant2=decoded[1],
                    balance1=decoded[2],
                    balance2=decoded[3],
                    block_number=log["blockNumber"],
                    tx_hash=log["transactionHash"].hex(),
                ))

            # Fetch ChannelClosed events
            closed_logs = self._w3.eth.get_logs({
                "address": self._contract_address,
                "fromBlock": from_block,
                "toBlock": to_block,
                "topics": [self._closed_topic],
            })

            for log in closed_logs:
                channel_id = "0x" + log["topics"][1].hex()
                decoded = self._w3.codec.decode(["uint256", "uint256"], log["data"])
                events.append(OnChainChannelEvent(
                    channel_id=channel_id,
                    event_type="ChannelClosed",
                    participant1=None,
                    participant2=None,
                    balance1=decoded[0],
                    balance2=decoded[1],
                    block_number=log["blockNumber"],
                    tx_hash=log["transactionHash"].hex(),
                ))

            # Fetch DisputeRaised events
            dispute_logs = self._w3.eth.get_logs({
                "address": self._contract_address,
                "fromBlock": from_block,
                "toBlock": to_block,
                "topics": [self._dispute_topic],
            })

            for log in dispute_logs:
                channel_id = "0x" + log["topics"][1].hex()
                raiser = Web3.to_checksum_address("0x" + log["topics"][2].hex()[-40:])
                events.append(OnChainChannelEvent(
                    channel_id=channel_id,
                    event_type="DisputeRaised",
                    participant1=raiser,
                    participant2=None,
                    balance1=None,
                    balance2=None,
                    block_number=log["blockNumber"],
                    tx_hash=log["transactionHash"].hex(),
                ))

        except Exception as e:
            logger.error(f"Failed to fetch channel logs: {e}")

        return events

    async def get_current_block(self) -> int:
        return await self._w3.eth.block_number

    async def get_safe_block(self) -> int:
        """Retorna o último bloco seguro, aplicando buffer de latência para evitar reorgs."""
        current = await self._w3.eth.block_number
        return max(0, current - config.latency_buffer_blocks)


# =============================================================================
# Event Store Client
# =============================================================================


class ChannelEventStoreReader:
    """Reads state channel events from the PostgreSQL event store."""

    def __init__(self, database_url: str):
        self._engine = create_async_engine(database_url)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession
        )

    async def get_channel_events(
        self, since: datetime
    ) -> List[OffChainChannelEvent]:
        """Fetch state channel events from the event store."""
        async with self._session_factory() as session:
            query = text("""
                SELECT
                    e.event_id,
                    e.aggregate_id,
                    e.event_type,
                    e.data,
                    e.occurred_at
                FROM events e
                WHERE e.event_type IN (
                    'StateChannelCreated',
                    'StateChannelUpdate',
                    'StateChannelClosed',
                    'BillingSessionSettled'
                )
                AND e.occurred_at >= :since
                ORDER BY e.occurred_at ASC
            """)

            result = await session.execute(query, {"since": since})
            rows = result.fetchall()

            events = []
            for row in rows:
                data = row.data if isinstance(row.data, dict) else json.loads(row.data)
                events.append(
                    OffChainChannelEvent(
                        event_id=str(row.event_id),
                        channel_id=row.aggregate_id,
                        event_type=row.event_type,
                        data=data,
                        occurred_at=row.occurred_at,
                    )
                )
            return events

    async def close(self):
        await self._engine.dispose()


# =============================================================================
# Matching Engine
# =============================================================================


class ChannelMatcher:
    """Matches on-chain channel events with off-chain events."""

    def match(
        self,
        on_chain: List[OnChainChannelEvent],
        off_chain: List[OffChainChannelEvent],
    ) -> StateChannelReconciliationReport:
        """Match on-chain and off-chain channel records."""
        report = StateChannelReconciliationReport(
            run_id=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=config.reconciliation_window_hours),
            window_end=datetime.now(timezone.utc),
        )

        report.total_on_chain = len(on_chain)
        report.total_off_chain = len(off_chain)
        report.on_chain_events = on_chain
        report.off_chain_events = off_chain

        # Count pending disputes
        report.pending_disputes = sum(
            1 for e in on_chain if e.event_type == "DisputeRaised"
        )

        # Build off-chain channel state
        off_chain_channels: Dict[str, str] = {}  # channel_id -> latest status
        for event in off_chain:
            if event.event_type == "StateChannelCreated":
                off_chain_channels[event.channel_id] = "open"
            elif event.event_type in ("StateChannelClosed", "BillingSessionSettled"):
                off_chain_channels[event.channel_id] = "closed"

        # Build on-chain channel state
        on_chain_channels: Dict[str, str] = {}
        for event in on_chain:
            if event.event_type == "ChannelCreated":
                on_chain_channels[event.channel_id] = "open"
            elif event.event_type == "ChannelClosed":
                on_chain_channels[event.channel_id] = "closed"
            elif event.event_type == "DisputeRaised":
                on_chain_channels[event.channel_id] = "disputed"

        # Match
        all_channels = set(list(on_chain_channels.keys()) + list(off_chain_channels.keys()))

        for channel_id in all_channels:
            on_state = on_chain_channels.get(channel_id)
            off_state = off_chain_channels.get(channel_id)

            if on_state and off_state:
                if on_state == off_state:
                    report.matched += 1
                else:
                    report.state_mismatches += 1
            elif on_state and not off_state:
                report.on_chain_only += 1
            elif off_state and not on_state:
                report.off_chain_only += 1

        return report


# =============================================================================
# Report Generation
# =============================================================================


def generate_report_summary(report: StateChannelReconciliationReport) -> str:
    """Generate a human-readable summary."""
    lines = [
        "=" * 60,
        f"STATE CHANNEL RECONCILIATION REPORT - {report.run_id}",
        f"Timestamp: {report.timestamp.isoformat()}",
        f"Window: {report.window_start.isoformat()} to {report.window_end.isoformat()}",
        "=" * 60,
        "",
        f"On-chain events:       {report.total_on_chain}",
        f"Off-chain events:      {report.total_off_chain}",
        "",
        f"✅ Matched:            {report.matched}",
        f"⚠️  On-chain only:     {report.on_chain_only}",
        f"⚠️  Off-chain only:    {report.off_chain_only}",
        f"❌ State mismatches:   {report.state_mismatches}",
        "",
        f"⚠️  Pending disputes:  {report.pending_disputes}",
        "",
        f"Discrepancy rate:      {report.discrepancy_rate:.4%}",
        f"Threshold:             {config.max_discrepancy_rate:.4%}",
        f"Status:                {'✅ HEALTHY' if report.is_healthy else '❌ UNHEALTHY'}",
        "",
        "=" * 60,
    ]
    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================


async def run_reconciliation(
    hours: int = 24,
    output_dir: Optional[str] = None,
) -> StateChannelReconciliationReport:
    """Run state channel reconciliation."""
    logger.info(f"Starting state channel reconciliation (window: {hours}h)")

    blockchain = BlockchainChannelReader(
        rpc_url=config.rpc_url,
        contract_address=config.payment_verifier_address,
    )
    event_store = ChannelEventStoreReader(database_url=config.database_url)
    matcher = ChannelMatcher()

    try:
        current_block = await blockchain.get_current_block()
        blocks_in_window = hours * 3600 // 2
        from_block = max(0, current_block - blocks_in_window)

        on_chain = await blockchain.get_channel_events(from_block, current_block)
        logger.info(f"Found {len(on_chain)} on-chain channel events")

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        off_chain = await event_store.get_channel_events(since)
        logger.info(f"Found {len(off_chain)} off-chain channel events")

        report = matcher.match(on_chain, off_chain)
        summary = generate_report_summary(report)
        print(summary)

        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            json_path = output_path / f"channel_reconciliation_{report.run_id}.json"
            json_path.write_text(json.dumps(asdict(report), default=str, indent=2))

        return report
    finally:
        await event_store.close()


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile on-chain state channels with off-chain event store"
    )
    parser.add_argument(
        "--hours", type=int, default=config.reconciliation_window_hours
    )
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    report = asyncio.run(
        run_reconciliation(hours=args.hours, output_dir=args.output_dir)
    )

    if not report.is_healthy:
        exit(1)


if __name__ == "__main__":
    main()
