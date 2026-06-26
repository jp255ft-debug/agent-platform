"""Payment simulator for DePIN State Channel verification flows.

This simulator generates realistic payment events including:
- State channel proof generation (success)
- Kill-switch triggers (budget exceeded)
- Payment failures (insufficient funds, invalid signature, etc.)
- Batch payment processing
- Credit risk verification

Usage:
    python -m agents.simulator.payment_simulator --rate 3 --failure-rate 0.1
    python -m agents.simulator.payment_simulator --duration 180 --verbose
"""

import argparse
import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Failure modes for realistic simulation (DePIN Procurement)
FAILURE_MODES = [
    "budget_exceeded_kill_switch",
    "insufficient_funds",
    "invalid_signature",
    "expired_nonce",
    "gas_limit_exceeded",
    "contract_paused",
    "unauthorized_sender",
    "state_channel_expired",
    "delegation_revoked",
]


@dataclass
class PaymentSimulationConfig:
    """Configuration for payment simulation."""

    events_per_second: float = 3.0
    duration_seconds: Optional[int] = None
    failure_rate: float = 0.1
    batch_size: int = 1
    output_file: Optional[str] = None
    max_budget_per_agent: float = 50.0  # USDC max budget for kill-switch


class PaymentSimulator:
    """Simulates payment verification events for DePIN State Channels.

    Emulates the credit risk verification loop:
    1. Billing tick arrives from GPU lease
    2. Verifier checks accumulated spend vs delegated budget
    3. If within budget → emit state channel proof
    4. If over budget → trigger kill-switch (disconnect GPU node)
    """

    def __init__(self, config: PaymentSimulationConfig):
        self.config = config
        self.events_generated = 0
        self.successful_payments = 0
        self.failed_payments = 0
        self.kill_switch_triggers = 0
        self.bad_debt_prevented = 0
        self._running = False
        # Track accumulated spend per agent (simulated CQRS read model)
        self._agent_spend: dict[str, float] = {}

    def _verify_credit_risk(self, agent_id: str, amount_usdc: float) -> bool:
        """Verify if agent has enough budget remaining.

        Returns True if within budget, False if kill-switch should trigger.
        """
        current_spend = self._agent_spend.get(agent_id, 0.0)
        new_spend = current_spend + amount_usdc

        if new_spend >= self.config.max_budget_per_agent:
            logger.warning(
                f"🚨 KILL-SWITCH: Agent {agent_id} spent ${new_spend:.2f} USDC "
                f"(limit: ${self.config.max_budget_per_agent:.2f})"
            )
            self.kill_switch_triggers += 1
            self.bad_debt_prevented += amount_usdc
            return False

        self._agent_spend[agent_id] = new_spend
        return True

    def _generate_payment_event(self) -> dict:
        """Generate a payment event with DePIN State Channel semantics."""
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        amount_usdc = random.uniform(1.0, 25.0)  # USDC amount per tick
        is_failure = random.random() < self.config.failure_rate

        # Credit risk verification (simulates CQRS read model check)
        within_budget = self._verify_credit_risk(agent_id, amount_usdc)

        base_event = {
            "event_id": str(uuid.uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "agent_id": agent_id,
                "sender": f"0x{uuid.uuid4().hex[:40]}",
                "recipient": f"0x{uuid.uuid4().hex[:40]}",
                "amount_micro_usdc": int(amount_usdc * 1_000_000),
                "amount_usdc": round(amount_usdc, 6),
                "nonce": random.randint(1, 1000),
                "tx_hash": f"0x{uuid.uuid4().hex[:64]}",
                "block_number": random.randint(10000000, 20000000),
                "provider_id": f"provider_{random.choice(['io-net', 'render', 'akash', 'gpu-network'])}",
            },
        }

        if not within_budget:
            # Kill-switch triggered: budget exceeded
            base_event["event_type"] = "PaymentFailed"
            base_event["data"]["error"] = "budget_exceeded_kill_switch"
            base_event["data"]["kill_switch_triggered"] = True
            base_event["data"]["accumulated_spend_usdc"] = round(
                self._agent_spend.get(agent_id, 0.0), 6
            )
            base_event["data"]["budget_limit_usdc"] = self.config.max_budget_per_agent
            self.failed_payments += 1
        elif is_failure:
            base_event["event_type"] = "PaymentFailed"
            base_event["data"]["error"] = random.choice(FAILURE_MODES)
            base_event["data"]["gas_used"] = random.randint(20000, 100000)
            self.failed_payments += 1
        else:
            base_event["event_type"] = "PaymentVerified"
            base_event["data"]["gas_used"] = random.randint(30000, 150000)
            base_event["data"]["state_channel_proof"] = f"proof_{uuid.uuid4().hex[:32]}"
            self.successful_payments += 1

        self.events_generated += 1
        return base_event

    async def _output_event(self, event: dict):
        """Output event to console or file."""
        if self.config.output_file:
            with open(self.config.output_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        else:
            status = "✅" if event["event_type"] == "PaymentVerified" else "❌"
            print(
                f"[{event['occurred_at'][11:19]}] {status} "
                f"{event['event_type']:<20} "
                f"amount={event['data']['amount']:<8} "
                f"sender={event['data']['sender'][:10]}..."
            )

    async def run(self):
        """Run the payment simulation."""
        logger.info(
            f"Starting payment simulation: "
            f"{self.config.events_per_second} events/sec, "
            f"{self.config.failure_rate:.0%} failure rate"
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

                # Generate batch
                for _ in range(self.config.batch_size):
                    event = self._generate_payment_event()
                    await self._output_event(event)

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            self._print_summary()

    def _print_summary(self):
        """Print simulation summary."""
        total = self.successful_payments + self.failed_payments
        success_rate = (
            (self.successful_payments / total * 100) if total > 0 else 0
        )
        print("\n" + "=" * 60)
        print("PAYMENT SIMULATION SUMMARY")
        print("=" * 60)
        print(f"Total events:        {self.events_generated}")
        print(f"Successful payments: {self.successful_payments}")
        print(f"Failed payments:     {self.failed_payments}")
        print(f"Success rate:        {success_rate:.1f}%")
        print("=" * 60)

    def stop(self):
        self._running = False


def main():
    parser = argparse.ArgumentParser(
        description="Simulate payment verification events for testing"
    )
    parser.add_argument("--rate", type=float, default=3.0)
    parser.add_argument("--duration", type=int, help="Duration in seconds")
    parser.add_argument(
        "--failure-rate", type=float, default=0.1, help="0.0-1.0"
    )
    parser.add_argument("--batch", type=int, default=1, help="Batch size")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = PaymentSimulationConfig(
        events_per_second=args.rate,
        duration_seconds=args.duration,
        failure_rate=args.failure_rate,
        batch_size=args.batch,
        output_file=args.output,
    )

    simulator = PaymentSimulator(config)
    asyncio.run(simulator.run())


if __name__ == "__main__":
    main()
