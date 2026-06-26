"""Agent activity simulator for testing billing and consumption flows.

This simulator generates realistic agent activity including:
- Agent registration events
- Billing session start/complete cycles
- Resource consumption events
- Payment verification events

Usage:
    python -m agents.simulator.agent_simulator --agents 10 --rate 5
    python -m agents.simulator.agent_simulator --duration 300 --verbose
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

# Resource types and their typical costs (DePIN GPU Procurement)
RESOURCE_TYPES = {
    "GPU_COMPUTE_TFLOPS": {"cost_range": (10, 1000), "unit": "tflops", "p_gpu": 0.00015},
    "GPU_VRAM": {"cost_range": (5, 300), "unit": "gb_hour", "p_gpu": 0.00008},
    "INFERENCE_TOKEN": {"cost_range": (50, 5000), "unit": "tokens", "p_token": 0.000002},
    "ZK_PROOF": {"cost_range": (100, 2000), "unit": "proofs", "p_gpu": 0.00030},
    "DEEPSEEK_R1": {"cost_range": (200, 8000), "unit": "reasoning_tokens", "p_token": 0.000005},
}

# DePIN provider IDs for realistic simulation
DEPIN_PROVIDERS = [
    "io-net",
    "render-network",
    "akash-network",
    "gpu-network",
    "nosana",
    "clore-ai",
]

# Event types to simulate (DePIN Procurement semantics)
EVENT_TYPES = [
    "AgentRegistered",
    "BillingSessionStarted",
    "ResourceConsumed",
    "ResourceConsumedV2",  # DePIN V2 with cost_micro_usdc + provider_id
    "BillingSessionCompleted",
    "PaymentVerified",
    "InvoiceGenerated",
]



@dataclass
class SimulatedAgent:
    """Represents a simulated agent."""

    agent_id: str
    wallet_address: str
    active_sessions: int = 0
    total_consumption: int = 0
    total_revenue: int = 0
    session_count: int = 0


@dataclass
class SimulationConfig:
    """Configuration for the agent simulator."""

    num_agents: int = 10
    events_per_second: float = 5.0
    duration_seconds: Optional[int] = None
    failure_rate: float = 0.05  # 5% chance of payment failure
    output_file: Optional[str] = None
    kafka_topic: Optional[str] = None


class AgentSimulator:
    """Simulates agent activity for testing."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.agents: list[SimulatedAgent] = []
        self.events_generated = 0
        self._running = False

    def _create_agent(self) -> SimulatedAgent:
        """Create a simulated agent."""
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        wallet = f"0x{uuid.uuid4().hex[:40]}"
        return SimulatedAgent(
            agent_id=agent_id,
            wallet_address=wallet,
        )

    def _generate_event(self, agent: SimulatedAgent) -> dict:
        """Generate a random event for an agent."""
        event_type = random.choice(EVENT_TYPES)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "aggregate_id": agent.agent_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "data": {},
        }

        if event_type == "AgentRegistered":
            event["data"] = {
                "wallet_address": agent.wallet_address,
                "metadata": {"simulated": True},
            }

        elif event_type == "BillingSessionStarted":
            agent.active_sessions += 1
            agent.session_count += 1
            event["data"] = {
                "session_id": f"session_{uuid.uuid4().hex[:12]}",
                "agent_id": agent.agent_id,
            }

        elif event_type == "ResourceConsumed":
            resource = random.choice(list(RESOURCE_TYPES.keys()))
            cost = random.randint(*RESOURCE_TYPES[resource]["cost_range"])
            agent.total_consumption += cost
            event["data"] = {
                "resource_type": resource,
                "amount": cost,
                "unit": RESOURCE_TYPES[resource]["unit"],
                "session_id": f"session_{uuid.uuid4().hex[:12]}",
            }

        elif event_type == "ResourceConsumedV2":
            """DePIN V2 event with cost_micro_usdc and provider_id.
            
            Simula a equação de inferência em tempo real:
            cost = (p_gpu * tflops_used * delta_t) + (p_token * n_tokens)
            """
            resource = random.choice(list(RESOURCE_TYPES.keys()))
            specs = RESOURCE_TYPES[resource]
            amount = random.randint(*specs["cost_range"])
            delta_t = random.randint(1, 10)  # seconds
            p_gpu = specs.get("p_gpu", 0.00015)
            p_token = specs.get("p_token", 0.000002)
            n_tokens = random.randint(100, 3000)
            
            # Cálculo do custo em micro USDC (1 USDC = 1_000_000 micro USDC)
            cost_usdc = (p_gpu * amount * delta_t) + (p_token * n_tokens)
            cost_micro_usdc = int(cost_usdc * 1_000_000)
            
            agent.total_consumption += int(cost_usdc)
            event["data"] = {
                "resource_type": resource,
                "amount": amount,
                "unit": specs["unit"],
                "cost_micro_usdc": cost_micro_usdc,
                "cost_usdc": round(cost_usdc, 6),
                "provider_id": random.choice(DEPIN_PROVIDERS),
                "session_id": f"session_{uuid.uuid4().hex[:12]}",
                "delta_t_seconds": delta_t,
                "tokens_used": n_tokens,
            }

        elif event_type == "BillingSessionCompleted":

            if agent.active_sessions > 0:
                agent.active_sessions -= 1
                amount = random.randint(100, 5000)
                agent.total_revenue += amount
                event["data"] = {
                    "session_id": f"session_{uuid.uuid4().hex[:12]}",
                    "amount": amount,
                    "duration_seconds": random.randint(10, 300),
                }

        elif event_type == "PaymentVerified":
            amount = random.randint(100, 5000)
            event["data"] = {
                "sender": agent.wallet_address,
                "recipient": f"0x{uuid.uuid4().hex[:40]}",
                "amount": amount,
                "nonce": agent.session_count,
                "tx_hash": f"0x{uuid.uuid4().hex[:64]}",
            }

        elif event_type == "InvoiceGenerated":
            amount = random.randint(1000, 50000)
            event["data"] = {
                "invoice_id": f"inv_{uuid.uuid4().hex[:12]}",
                "agent_id": agent.agent_id,
                "amount": amount,
                "due_date": datetime.now(timezone.utc).isoformat(),
            }

        # Simulate failures
        if random.random() < self.config.failure_rate and event_type in (
            "PaymentVerified",
            "BillingSessionCompleted",
        ):
            event["event_type"] = event_type.replace("Verified", "Failed").replace(
                "Completed", "Failed"
            )
            event["data"]["error"] = "simulated_failure"

        return event

    async def _output_event(self, event: dict):
        """Output an event to console, file, or Kafka."""
        if self.config.output_file:
            with open(self.config.output_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        elif self.config.kafka_topic:
            # Kafka output would go here
            pass
        else:
            # Console output (compact)
            print(
                f"[{event['occurred_at'][11:19]}] "
                f"{event['event_type']:<30} "
                f"{event['aggregate_id'][:20]}"
            )

    async def run(self):
        """Run the simulation."""
        logger.info(
            f"Starting simulation: {self.config.num_agents} agents, "
            f"{self.config.events_per_second} events/sec"
        )

        self._running = True
        self.agents = [self._create_agent() for _ in range(self.config.num_agents)]

        start_time = time.time()
        interval = 1.0 / self.config.events_per_second

        try:
            while self._running:
                # Check duration
                if self.config.duration_seconds:
                    elapsed = time.time() - start_time
                    if elapsed >= self.config.duration_seconds:
                        logger.info(f"Simulation completed after {elapsed:.0f}s")
                        break

                # Pick a random agent and generate event
                agent = random.choice(self.agents)
                event = self._generate_event(agent)
                self.events_generated += 1

                await self._output_event(event)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Simulation cancelled")
        finally:
            self._running = False
            self._print_summary()

    def _print_summary(self):
        """Print simulation summary."""
        print("\n" + "=" * 60)
        print("SIMULATION SUMMARY")
        print("=" * 60)
        print(f"Agents:          {len(self.agents)}")
        print(f"Events generated: {self.events_generated}")
        print(f"Total revenue:    {sum(a.total_revenue for a in self.agents)}")
        print(f"Total consumption: {sum(a.total_consumption for a in self.agents)}")
        print(f"Total sessions:   {sum(a.session_count for a in self.agents)}")
        print("=" * 60)

    def stop(self):
        """Stop the simulation."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(
        description="Simulate agent activity for testing"
    )
    parser.add_argument(
        "--agents", type=int, default=10, help="Number of agents to simulate"
    )
    parser.add_argument(
        "--rate", type=float, default=5.0, help="Events per second"
    )
    parser.add_argument(
        "--duration", type=int, help="Duration in seconds (default: unlimited)"
    )
    parser.add_argument(
        "--failure-rate",
        type=float,
        default=0.05,
        help="Probability of payment failure (0.0-1.0)",
    )
    parser.add_argument(
        "--output", help="Output file path (JSON lines format)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = SimulationConfig(
        num_agents=args.agents,
        events_per_second=args.rate,
        duration_seconds=args.duration,
        failure_rate=args.failure_rate,
        output_file=args.output,
    )

    simulator = AgentSimulator(config)
    asyncio.run(simulator.run())


if __name__ == "__main__":
    main()
