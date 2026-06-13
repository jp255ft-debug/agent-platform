"""Delegation simulator for testing EIP-7702 delegation flows.

This simulator generates delegation events including:
- Delegation creation with expiration
- Delegation revocation
- Delegation expiration scenarios
- Concurrent delegation management

Usage:
    python -m agents.simulator.delegation_simulator --agents 5 --rate 2
    python -m agents.simulator.delegation_simulator --duration 120 --verbose
"""

import argparse
import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SimulatedDelegation:
    """Represents a simulated delegation."""

    agent_id: str
    delegate_address: str
    created_at: datetime
    expires_at: datetime
    active: bool = True


@dataclass
class DelegationSimulationConfig:
    """Configuration for delegation simulation."""

    num_agents: int = 5
    events_per_second: float = 2.0
    duration_seconds: Optional[int] = None
    max_delegations_per_agent: int = 3
    delegation_ttl_minutes: int = 60
    output_file: Optional[str] = None


class DelegationSimulator:
    """Simulates delegation activity for testing."""

    def __init__(self, config: DelegationSimulationConfig):
        self.config = config
        self.delegations: dict[str, list[SimulatedDelegation]] = {}
        self.events_generated = 0
        self._running = False

    def _generate_delegation_event(self) -> dict:
        """Generate a delegation event."""
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        delegate = f"0x{uuid.uuid4().hex[:40]}"

        if agent_id not in self.delegations:
            self.delegations[agent_id] = []

        active_delegations = [d for d in self.delegations[agent_id] if d.active]

        # Decide action: create or revoke
        if (
            len(active_delegations) < self.config.max_delegations_per_agent
            and random.random() < 0.7
        ):
            # Create delegation
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(
                minutes=random.randint(1, self.config.delegation_ttl_minutes)
            )

            delegation = SimulatedDelegation(
                agent_id=agent_id,
                delegate_address=delegate,
                created_at=now,
                expires_at=expires_at,
                active=True,
            )
            self.delegations[agent_id].append(delegation)

            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "AgentDelegated",
                "aggregate_id": agent_id,
                "occurred_at": now.isoformat(),
                "data": {
                    "delegate": delegate,
                    "expires_at": int(expires_at.timestamp()),
                    "block_number": random.randint(10000000, 20000000),
                },
            }
        elif active_delegations:
            # Revoke delegation
            delegation = random.choice(active_delegations)
            delegation.active = False

            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "AgentDelegationRevoked",
                "aggregate_id": agent_id,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "delegate": delegation.delegate_address,
                    "reason": "simulated_revocation",
                },
            }
        else:
            # Fallback: create delegation
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=30)
            delegation = SimulatedDelegation(
                agent_id=agent_id,
                delegate_address=delegate,
                created_at=now,
                expires_at=expires_at,
                active=True,
            )
            self.delegations[agent_id].append(delegation)

            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "AgentDelegated",
                "aggregate_id": agent_id,
                "occurred_at": now.isoformat(),
                "data": {
                    "delegate": delegate,
                    "expires_at": int(expires_at.timestamp()),
                    "block_number": random.randint(10000000, 20000000),
                },
            }

        self.events_generated += 1
        return event

    async def _output_event(self, event: dict):
        """Output event to console or file."""
        if self.config.output_file:
            with open(self.config.output_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        else:
            print(
                f"[{event['occurred_at'][11:19]}] "
                f"{event['event_type']:<30} "
                f"{event['aggregate_id'][:20]} -> "
                f"{event['data'].get('delegate', 'N/A')[:10]}..."
            )

    async def run(self):
        """Run the delegation simulation."""
        logger.info(
            f"Starting delegation simulation: {self.config.num_agents} agents"
        )

        self._running = True
        start_time = time.time()
        interval = 1.0 / self.config.events_per_second

        try:
            while self._running:
                if self.config.duration_seconds:
                    elapsed = time.time() - start_time
                    if elapsed >= self.config.duration_seconds:
                        break

                event = self._generate_delegation_event()
                await self._output_event(event)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            self._print_summary()

    def _print_summary(self):
        """Print simulation summary."""
        total_active = sum(
            1 for deps in self.delegations.values() for d in deps if d.active
        )
        total_expired = sum(
            1
            for deps in self.delegations.values()
            for d in deps
            if not d.active
        )
        print("\n" + "=" * 60)
        print("DELEGATION SIMULATION SUMMARY")
        print("=" * 60)
        print(f"Events generated:     {self.events_generated}")
        print(f"Total delegations:    {total_active + total_expired}")
        print(f"Active delegations:   {total_active}")
        print(f"Revoked/expired:      {total_expired}")
        print("=" * 60)

    def stop(self):
        self._running = False


def main():
    parser = argparse.ArgumentParser(
        description="Simulate delegation activity for testing"
    )
    parser.add_argument("--agents", type=int, default=5)
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument("--duration", type=int, help="Duration in seconds")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = DelegationSimulationConfig(
        num_agents=args.agents,
        events_per_second=args.rate,
        duration_seconds=args.duration,
        output_file=args.output,
    )

    simulator = DelegationSimulator(config)
    asyncio.run(simulator.run())


if __name__ == "__main__":
    main()
