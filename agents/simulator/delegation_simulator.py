"""Delegation simulator for testing EIP-7702 delegation flows.

This simulator generates delegation events including:
- Delegation creation with expiration (delegate)
- Gasless delegation via EIP-712 typed signatures (delegateBySig)
- Delegation revocation (revoke / revokeBySig)
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

# EIP-712 domain separator for gasless delegation (matching AgentDelegation.sol)
EIP712_DOMAIN = {
    "name": "AgentDelegation",
    "version": "1",
    "chainId": 84532,  # Base Sepolia
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

# EIP-712 type definitions for delegateBySig
DELEGATE_BY_SIG_TYPES = {
    "Delegation": [
        {"name": "delegate", "type": "address"},
        {"name": "expiry", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
    ],
}

# EIP-712 type definitions for revokeBySig
REVOKE_BY_SIG_TYPES = {
    "Revocation": [
        {"name": "delegate", "type": "address"},
        {"name": "nonce", "type": "uint256"},
    ],
}


@dataclass
class SimulatedDelegation:
    """Represents a simulated delegation."""

    agent_id: str
    delegate_address: str
    created_at: datetime
    expires_at: datetime
    active: bool = True
    is_gasless: bool = False  # True if created via delegateBySig


@dataclass
class DelegationSimulationConfig:
    """Configuration for delegation simulation."""

    num_agents: int = 5
    events_per_second: float = 2.0
    duration_seconds: Optional[int] = None
    max_delegations_per_agent: int = 3
    delegation_ttl_minutes: int = 60
    gasless_probability: float = 0.4  # 40% chance of using delegateBySig
    output_file: Optional[str] = None


class DelegationSimulator:
    """Simulates delegation activity for testing."""

    def __init__(self, config: DelegationSimulationConfig):
        self.config = config
        self.delegations: dict[str, list[SimulatedDelegation]] = {}
        self.events_generated = 0
        self._running = False
        # Track nonces per agent for EIP-712 replay protection
        self._nonces: dict[str, int] = {}

    def _get_next_nonce(self, agent_id: str) -> int:
        """Get next nonce for EIP-712 signature."""
        nonce = self._nonces.get(agent_id, 0)
        self._nonces[agent_id] = nonce + 1
        return nonce

    def _generate_eip712_signature(self, message: dict, types: dict) -> str:
        """Simulate EIP-712 typed signature generation.

        In production, this would use eth_signTypedData_v4.
        Here we generate a deterministic mock signature.
        """
        domain_hash = uuid.uuid5(
            uuid.NAMESPACE_DNS,
            json.dumps(EIP712_DOMAIN, sort_keys=True),
        ).hex[:32]
        message_hash = uuid.uuid5(
            uuid.NAMESPACE_DNS,
            json.dumps(message, sort_keys=True),
        ).hex[:32]

        # Mock EIP-712 signature: v (1 byte) + r (32 bytes) + s (32 bytes)
        return (
            f"0x{domain_hash}{message_hash}"
            f"{uuid.uuid4().hex[:64]}"
            f"{uuid.uuid4().hex[:64]}"
            f"1b"
        )

    def _generate_delegation_event(self) -> dict:
        """Generate a delegation event with optional gasless flow."""
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        delegate = f"0x{uuid.uuid4().hex[:40]}"

        if agent_id not in self.delegations:
            self.delegations[agent_id] = []

        active_delegations = [d for d in self.delegations[agent_id] if d.active]
        use_gasless = random.random() < self.config.gasless_probability

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
                is_gasless=use_gasless,
            )
            self.delegations[agent_id].append(delegation)

            if use_gasless:
                # Gasless delegation via delegateBySig (EIP-712)
                nonce = self._get_next_nonce(agent_id)
                message = {
                    "delegate": delegate,
                    "expiry": int(expires_at.timestamp()),
                    "nonce": nonce,
                }
                signature = self._generate_eip712_signature(
                    message, DELEGATE_BY_SIG_TYPES
                )

                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "AgentDelegated",
                    "aggregate_id": agent_id,
                    "occurred_at": now.isoformat(),
                    "data": {
                        "delegate": delegate,
                        "expires_at": int(expires_at.timestamp()),
                        "nonce": nonce,
                        "signature": signature,
                        "gasless": True,
                        "eip712_domain": EIP712_DOMAIN,
                        "eip712_types": DELEGATE_BY_SIG_TYPES,
                        "block_number": random.randint(10000000, 20000000),
                    },
                }
            else:
                # On-chain delegation via delegate()
                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "AgentDelegated",
                    "aggregate_id": agent_id,
                    "occurred_at": now.isoformat(),
                    "data": {
                        "delegate": delegate,
                        "expires_at": int(expires_at.timestamp()),
                        "gasless": False,
                        "block_number": random.randint(10000000, 20000000),
                    },
                }
        elif active_delegations:
            # Revoke delegation
            delegation = random.choice(active_delegations)
            delegation.active = False

            use_gasless_revoke = use_gasless and delegation.is_gasless

            if use_gasless_revoke:
                # Gasless revocation via revokeBySig (EIP-712)
                nonce = self._get_next_nonce(agent_id)
                message = {
                    "delegate": delegation.delegate_address,
                    "nonce": nonce,
                }
                signature = self._generate_eip712_signature(
                    message, REVOKE_BY_SIG_TYPES
                )

                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "AgentDelegationRevoked",
                    "aggregate_id": agent_id,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "delegate": delegation.delegate_address,
                        "reason": "simulated_revocation",
                        "nonce": nonce,
                        "signature": signature,
                        "gasless": True,
                        "eip712_domain": EIP712_DOMAIN,
                        "eip712_types": REVOKE_BY_SIG_TYPES,
                    },
                }
            else:
                # On-chain revocation via revoke()
                event = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "AgentDelegationRevoked",
                    "aggregate_id": agent_id,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "delegate": delegation.delegate_address,
                        "reason": "simulated_revocation",
                        "gasless": False,
                    },
                }
        else:
            # Fallback: create delegation (on-chain)
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
                    "gasless": False,
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
            gasless_tag = "⚡" if event["data"].get("gasless") else "  "
            print(
                f"[{event['occurred_at'][11:19]}] {gasless_tag} "
                f"{event['event_type']:<30} "
                f"{event['aggregate_id'][:20]} -> "
                f"{event['data'].get('delegate', 'N/A')[:10]}..."
            )

    async def run(self):
        """Run the delegation simulation."""
        logger.info(
            f"Starting delegation simulation: {self.config.num_agents} agents, "
            f"{self.config.gasless_probability:.0%} gasless"
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
        total_gasless = sum(
            1
            for deps in self.delegations.values()
            for d in deps
            if d.is_gasless
        )
        print("\n" + "=" * 60)
        print("DELEGATION SIMULATION SUMMARY")
        print("=" * 60)
        print(f"Events generated:     {self.events_generated}")
        print(f"Total delegations:    {total_active + total_expired}")
        print(f"Active delegations:   {total_active}")
        print(f"Revoked/expired:      {total_expired}")
        print(f"Gasless (EIP-712):    {total_gasless}")
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
    parser.add_argument(
        "--gasless",
        type=float,
        default=0.4,
        help="Probability of gasless delegation (0.0-1.0)",
    )
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
        gasless_probability=args.gasless,
        output_file=args.output,
    )

    simulator = DelegationSimulator(config)
    asyncio.run(simulator.run())


if __name__ == "__main__":
    main()
