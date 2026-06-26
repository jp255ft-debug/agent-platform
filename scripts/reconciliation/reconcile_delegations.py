"""Delegation reconciliation: on-chain AgentDelegation state vs. off-chain event store.

This script:
1. Fetches DelegationCreated/DelegationRevoked events from the blockchain
2. Queries the event store for corresponding delegation events
3. Compares active delegations on-chain vs. off-chain
4. Detects stale/expired delegations
5. Generates a reconciliation report

Usage:
    python -m scripts.reconciliation.reconcile_delegations
    python -m scripts.reconciliation.reconcile_delegations --hours 48 --alert
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
class OnChainDelegation:
    """A delegation recorded on-chain."""

    agent: str
    delegate: str
    expires_at: int
    active: bool
    block_number: int
    tx_hash: str


@dataclass
class OffChainDelegationEvent:
    """A delegation event recorded in the event store."""

    event_id: str
    agent_id: str
    event_type: str  # AgentDelegated, AgentDelegationRevoked
    delegate: Optional[str]
    expires_at: Optional[int]
    occurred_at: datetime


@dataclass
class DelegationReconciliationReport:
    """Report for delegation reconciliation."""

    run_id: str
    timestamp: datetime
    window_start: datetime
    window_end: datetime

    total_on_chain: int = 0
    total_off_chain: int = 0
    matched: int = 0
    on_chain_only: int = 0
    off_chain_only: int = 0
    expired_on_chain: int = 0
    expired_off_chain: int = 0
    state_mismatches: int = 0

    on_chain_delegations: List[OnChainDelegation] = field(default_factory=list)
    off_chain_events: List[OffChainDelegationEvent] = field(default_factory=list)
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


class BlockchainDelegationReader:
    """Reads delegation events from the AgentDelegation contract."""

    DELEGATION_CREATED_SIG = "DelegationCreated(address,address,uint256,uint256,uint256)"
    DELEGATION_REVOKED_SIG = "DelegationRevoked(address,address)"

    def __init__(self, rpc_url: str, contract_address: Optional[str] = None):
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self._contract_address = (
            Web3.to_checksum_address(contract_address) if contract_address else None
        )
        self._created_topic = Web3.keccak(text=self.DELEGATION_CREATED_SIG).hex()
        self._revoked_topic = Web3.keccak(text=self.DELEGATION_REVOKED_SIG).hex()

    async def get_delegation_events(
        self, from_block: int, to_block: int
    ) -> List[OnChainDelegation]:
        """Fetch delegation events in a block range."""
        if not self._contract_address:
            logger.warning("No AgentDelegation contract address configured")
            return []

        delegations: Dict[str, OnChainDelegation] = {}

        try:
            # Fetch DelegationCreated events
            created_logs = self._w3.eth.get_logs({
                "address": self._contract_address,
                "fromBlock": from_block,
                "toBlock": to_block,
                "topics": [self._created_topic],
            })

            for log in created_logs:
                agent = Web3.to_checksum_address("0x" + log["topics"][1].hex()[-40:])
                delegate = Web3.to_checksum_address("0x" + log["topics"][2].hex()[-40:])
                decoded = self._w3.codec.decode(["uint256", "uint256", "uint256"], log["data"])
                expires_at = decoded[0]
                max_budget = decoded[1]
                nonce = decoded[2]

                delegations[agent.lower()] = OnChainDelegation(
                    agent=agent,
                    delegate=delegate,
                    expires_at=expires_at,
                    active=True,
                    block_number=log["blockNumber"],
                    tx_hash=log["transactionHash"].hex(),
                )

            # Fetch DelegationRevoked events
            revoked_logs = self._w3.eth.get_logs({
                "address": self._contract_address,
                "fromBlock": from_block,
                "toBlock": to_block,
                "topics": [self._revoked_topic],
            })

            for log in revoked_logs:
                agent = Web3.to_checksum_address("0x" + log["topics"][1].hex()[-40:])
                agent_key = agent.lower()
                if agent_key in delegations:
                    delegations[agent_key].active = False

        except Exception as e:
            logger.error(f"Failed to fetch delegation logs: {e}")

        return list(delegations.values())

    async def get_current_block(self) -> int:
        return self._w3.eth.block_number


# =============================================================================
# Event Store Client
# =============================================================================


class DelegationEventStoreReader:
    """Reads delegation events from the PostgreSQL event store."""

    def __init__(self, database_url: str):
        self._engine = create_async_engine(database_url)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession
        )

    async def get_delegation_events(
        self, since: datetime
    ) -> List[OffChainDelegationEvent]:
        """Fetch delegation events from the event store."""
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
                    'AgentDelegated',
                    'AgentDelegationRevoked'
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
                    OffChainDelegationEvent(
                        event_id=str(row.event_id),
                        agent_id=row.aggregate_id,
                        event_type=row.event_type,
                        delegate=data.get("delegate"),
                        expires_at=data.get("expires_at"),
                        occurred_at=row.occurred_at,
                    )
                )
            return events

    async def close(self):
        await self._engine.dispose()


# =============================================================================
# Matching Engine
# =============================================================================


class DelegationMatcher:
    """Matches on-chain delegations with off-chain events."""

    def match(
        self,
        on_chain: List[OnChainDelegation],
        off_chain: List[OffChainDelegationEvent],
    ) -> DelegationReconciliationReport:
        """Match on-chain and off-chain delegation records."""
        report = DelegationReconciliationReport(
            run_id=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=config.reconciliation_window_hours),
            window_end=datetime.now(timezone.utc),
        )

        report.total_on_chain = len(on_chain)
        report.total_off_chain = len(off_chain)
        report.on_chain_delegations = on_chain
        report.off_chain_events = off_chain

        # Build off-chain state by agent
        off_chain_state: Dict[str, bool] = {}  # agent -> has_active_delegation
        for event in off_chain:
            if event.event_type == "AgentDelegated":
                off_chain_state[event.agent_id.lower()] = True
            elif event.event_type == "AgentDelegationRevoked":
                off_chain_state[event.agent_id.lower()] = False

        # Match
        matched_agents: set = set()
        for delegation in on_chain:
            agent_key = delegation.agent.lower()
            matched_agents.add(agent_key)

            off_chain_active = off_chain_state.get(agent_key)
            now = int(datetime.now(timezone.utc).timestamp())

            # Check if expired on-chain
            if delegation.expires_at <= now:
                report.expired_on_chain += 1

            if off_chain_active is None:
                report.on_chain_only += 1
            elif off_chain_active != delegation.active:
                report.state_mismatches += 1
            else:
                report.matched += 1

        # Find off-chain only
        for agent_key in off_chain_state:
            if agent_key not in matched_agents:
                report.off_chain_only += 1

        # Count expired off-chain
        for event in off_chain:
            if event.expires_at and event.expires_at <= int(datetime.now(timezone.utc).timestamp()):
                report.expired_off_chain += 1

        return report


# =============================================================================
# Report Generation
# =============================================================================


def generate_report_summary(report: DelegationReconciliationReport) -> str:
    """Generate a human-readable summary."""
    lines = [
        "=" * 60,
        f"DELEGATION RECONCILIATION REPORT - {report.run_id}",
        f"Timestamp: {report.timestamp.isoformat()}",
        f"Window: {report.window_start.isoformat()} to {report.window_end.isoformat()}",
        "=" * 60,
        "",
        f"On-chain delegations:  {report.total_on_chain}",
        f"Off-chain events:      {report.total_off_chain}",
        "",
        f"✅ Matched:            {report.matched}",
        f"⚠️  On-chain only:     {report.on_chain_only}",
        f"⚠️  Off-chain only:    {report.off_chain_only}",
        f"❌ State mismatches:   {report.state_mismatches}",
        "",
        f"Expired on-chain:      {report.expired_on_chain}",
        f"Expired off-chain:     {report.expired_off_chain}",
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
) -> DelegationReconciliationReport:
    """Run delegation reconciliation."""
    logger.info(f"Starting delegation reconciliation (window: {hours}h)")

    blockchain = BlockchainDelegationReader(
        rpc_url=config.rpc_url,
        contract_address=config.agent_delegation_address,
    )
    event_store = DelegationEventStoreReader(database_url=config.database_url)
    matcher = DelegationMatcher()

    try:
        current_block = await blockchain.get_current_block()
        blocks_in_window = hours * 3600 // 2
        from_block = max(0, current_block - blocks_in_window)

        on_chain = await blockchain.get_delegation_events(from_block, current_block)
        logger.info(f"Found {len(on_chain)} on-chain delegation events")

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        off_chain = await event_store.get_delegation_events(since)
        logger.info(f"Found {len(off_chain)} off-chain delegation events")

        report = matcher.match(on_chain, off_chain)
        summary = generate_report_summary(report)
        print(summary)

        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            json_path = output_path / f"delegation_reconciliation_{report.run_id}.json"
            json_path.write_text(json.dumps(asdict(report), default=str, indent=2))

        return report
    finally:
        await event_store.close()


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile on-chain delegations with off-chain event store"
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
