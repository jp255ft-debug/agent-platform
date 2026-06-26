"""Locust smoke test for agent-platform API.

Run: locust -f scripts/load-test/smoke_test.py --headless -u 20 -r 5 --run-time 2m --host http://localhost:8000
"""
import random
from locust import HttpUser, task, between


class SmokeTestUser(HttpUser):
    """Simulates a user hitting the agent-platform API endpoints."""

    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Generate a random agent ID for this user."""
        self.agent_id = f"agent_{random.randint(10000, 99999)}"

    @task(3)
    def health_check(self):
        """GET /health - lightweight health check."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(2)
    def consume_resource(self):
        """POST /api/v1/consume - resource consumption endpoint."""
        payload = {
            "agent_id": self.agent_id,
            "resource_type": random.choice(["compute", "storage", "bandwidth"]),
            "amount": random.randint(1, 100),
            "x402_payment": {
                "chain_id": 1,
                "tx_hash": "0x" + "".join(random.choices("0123456789abcdef", k=64)),
                "amount": str(random.randint(1, 1000)),
                "token": "USDC",
            },
        }
        with self.client.post(
            "/api/v1/consume",
            json=payload,
            catch_response=True,
            name="/api/v1/consume",
        ) as response:
            if response.status_code in (200, 202):
                response.success()
            elif response.status_code == 429:
                # Rate limited - acceptable under load
                response.success()
            elif response.status_code == 402:
                # Payment required - acceptable if x402 validation fails
                response.success()
            else:
                response.failure(
                    f"Consume failed: {response.status_code} {response.text[:200]}"
                )

    @task(1)
    def list_agents(self):
        """GET /api/v1/agents - list agents."""
        with self.client.get(
            "/api/v1/agents",
            catch_response=True,
            name="/api/v1/agents",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"List agents failed: {response.status_code}"
                )
