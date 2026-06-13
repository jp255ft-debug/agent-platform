"""Payment simulator for testing on-chain payment verification flows.

This simulator generates realistic payment events including:
- Payment verification (success)
- Payment failures (insufficient funds, invalid signature, etc.)
- Payment retry scenarios
- Batch payment processing

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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Failure modes for realistic simulation
FAILURE_MODES = [
    "insufficient_funds",
    "invalid_signature",
    "expired_nonce",
    "gas_limit_exceeded",
    "contract_paused",
    "unauthorized_sender",
]


@dataclass
class PaymentSimulationConfig:
    """Configuration for payment simulation."""

    events_per_second: float = 3.0
    duration_seconds: Optional[int] = None
    failure_rate: float = 0.1
    batch_size: int = 1
    output_file: Optional[str] = None


class PaymentSimulator:
    """Simulates payment verification events for testing."""

    def __init__(self, config: PaymentSimulationConfig):
        self.config = config
        self.events_generated = 0
        self.successful_payments = 0
        self.failed_payments = 0
        self._running = False

    def _generate_payment_event(self) -> dict:
        """Generate a payment event."""
        is_failure = random.random() < self.config.failure_rate

        base_event = {
            "event_id": str(uuid.uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "sender": f"0x{uuid.uuid4().hex[:40]}",
                "recipient": f"0x{uuid.uuid4().hex[:40]}",
                "amount": random.randint(1000, 100000),
                "nonce": random.randint(1, 1000),
                "tx_hash": f"0x{uuid.uuid4().hex[:64]}",
                "block_number": random.randint(10000000, 20000000),
            },
        }

        if is_failure:
            base_event["event_type"] = "PaymentFailed"
            base_event["data"]["error"] = random.choice(FAILURE_MODES)
            base_event["data"]["gas_used"] = random.randint(20000, 100000)
            self.failed_payments += 1
        else:
            base_event["event_type"] = "PaymentVerified"
            base_event["data"]["gas_used"] = random.randint(30000, 150000)
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
