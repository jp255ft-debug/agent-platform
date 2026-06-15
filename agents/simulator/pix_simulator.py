"""Pix payment simulator for load testing.

Based on BUILD_GUIDE.md §16 — Camada 11: Integração com Sistema Financeiro Brasileiro.
Simulates Pix payment flows: QR Code generation, webhook callbacks, and reconciliation.

Usage:
    python -m agents.simulator.pix_simulator --rate 5 --duration 60
"""
import asyncio
import json
import logging
import random
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class PixSimulator:
    """Simulates Pix payment traffic for load testing.

    Generates QR Codes, simulates payments, and sends webhook callbacks
    to test the full Pix integration pipeline.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        rate: int = 2,
        duration: int = 30,
    ):
        """Initialize simulator.

        Args:
            base_url: Backend API base URL.
            rate: Number of payments per second.
            duration: Test duration in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._rate = rate
        self._duration = duration
        self._client = httpx.AsyncClient(timeout=30.0)

        # Metrics
        self._metrics = {
            "qr_codes_created": 0,
            "webhooks_sent": 0,
            "webhooks_accepted": 0,
            "errors": 0,
            "total_amount": Decimal("0"),
        }

    async def create_qr_code(self) -> Optional[str]:
        """Generate a Pix QR Code via the API.

        Returns:
            QR Code ID if successful, None otherwise.
        """
        amount = round(random.uniform(1.0, 1000.0), 2)
        payload = {
            "amount": amount,
            "description": f"Test payment {uuid.uuid4().hex[:8]}",
            "payer_name": random.choice(["Alice", "Bob", "Charlie", "Diana"]),
            "payer_document": f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
            "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
            "expires_in": 3600,
        }

        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/pix/qrcode",
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                self._metrics["qr_codes_created"] += 1
                self._metrics["total_amount"] += Decimal(str(amount))
                return data["qr_code_id"]
            else:
                logger.warning(
                    "QR Code creation failed: %d - %s",
                    response.status_code, response.text,
                )
                self._metrics["errors"] += 1
                return None

        except Exception as e:
            logger.error("QR Code creation error: %s", str(e))
            self._metrics["errors"] += 1
            return None

    async def send_webhook(self, qr_code_id: str) -> bool:
        """Simulate a Pix payment webhook callback.

        Args:
            qr_code_id: QR Code ID to confirm payment for.

        Returns:
            True if webhook was accepted, False otherwise.
        """
        webhook_payload = {
            "id": qr_code_id,
            "status": "paid",
            "amount": round(random.uniform(1.0, 1000.0), 2),
            "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
            "payer_name": random.choice(["Alice", "Bob", "Charlie", "Diana"]),
            "payer_document": f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
            "paid_at": datetime.utcnow().isoformat() + "Z",
            "created": datetime.utcnow().isoformat() + "Z",
        }

        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/pix/webhook",
                json=webhook_payload,
            )

            self._metrics["webhooks_sent"] += 1

            if response.status_code == 200:
                self._metrics["webhooks_accepted"] += 1
                return True
            else:
                logger.warning(
                    "Webhook rejected: %d - %s",
                    response.status_code, response.text,
                )
                self._metrics["errors"] += 1
                return False

        except Exception as e:
            logger.error("Webhook error: %s", str(e))
            self._metrics["errors"] += 1
            return False

    async def check_status(self, qr_code_id: str) -> Optional[str]:
        """Check the status of a Pix payment.

        Args:
            qr_code_id: QR Code ID to check.

        Returns:
            Status string if successful, None otherwise.
        """
        try:
            response = await self._client.get(
                f"{self._base_url}/api/v1/pix/{qr_code_id}/status",
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("status")
            else:
                logger.warning(
                    "Status check failed: %d - %s",
                    response.status_code, response.text,
                )
                return None

        except Exception as e:
            logger.error("Status check error: %s", str(e))
            return None

    async def run(self):
        """Run the simulation loop."""
        logger.info(
            "Starting Pix simulator: rate=%d/s, duration=%ds, target=%s",
            self._rate, self._duration, self._base_url,
        )

        start_time = time.time()
        payments_created = 0
        interval = 1.0 / self._rate

        while time.time() - start_time < self._duration:
            # Create QR Code
            qr_code_id = await self.create_qr_code()

            if qr_code_id:
                payments_created += 1

                # Simulate payment delay (100-500ms)
                await asyncio.sleep(random.uniform(0.1, 0.5))

                # Send webhook confirmation
                await self.send_webhook(qr_code_id)

                # Check status
                await self.check_status(qr_code_id)

            # Wait for rate limit
            await asyncio.sleep(interval)

        await self._client.aclose()
        self._print_summary(payments_created)

    def _print_summary(self, payments_created: int):
        """Print simulation summary."""
        logger.info("=" * 50)
        logger.info("Pix Simulation Complete")
        logger.info("=" * 50)
        logger.info("QR Codes Created:    %d", self._metrics["qr_codes_created"])
        logger.info("Webhooks Sent:       %d", self._metrics["webhooks_sent"])
        logger.info("Webhooks Accepted:   %d", self._metrics["webhooks_accepted"])
        logger.info("Errors:              %d", self._metrics["errors"])
        logger.info("Total Amount (BRL):  %s", self._metrics["total_amount"])
        logger.info("Success Rate:        %.1f%%",
            (self._metrics["webhooks_accepted"] / max(self._metrics["webhooks_sent"], 1)) * 100,
        )
        logger.info("=" * 50)


async def main():
    """Entry point for the Pix simulator."""
    import argparse

    parser = argparse.ArgumentParser(description="Pix Payment Simulator")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend API URL")
    parser.add_argument("--rate", type=int, default=2, help="Payments per second")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")

    args = parser.parse_args()

    simulator = PixSimulator(
        base_url=args.base_url,
        rate=args.rate,
        duration=args.duration,
    )

    await simulator.run()


if __name__ == "__main__":
    asyncio.run(main())
