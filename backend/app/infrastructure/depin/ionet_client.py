"""io.net API client for GPU leasing (VMaaS + CaaS + Intelligence)."""
import httpx
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.infrastructure.depin.ionet_models import (
    GPUHardware, PriceResponse, DeployResponse,
    DeploymentStatus, HardwareFilter,
)


class IonetClient:
    """
    HTTP client for io.net API.

    Supports two authentication methods:
    1. API Key (`sk-...`) → header `x-api-key`
    2. JWT Token (`io-v2-...`) → header `Authorization: Bearer <token>`

    Provides access to:
    - VMaaS: Virtual Machine as a Service (GPU cluster management)
    - CaaS: Container as a Service (container deployment on GPUs)
    - Intelligence: AI model inference and attestation
    """

    BASE_URL = "https://api.io.solutions/enterprise/v1/io-cloud"
    INTELLIGENCE_URL = "https://api.intelligence.io.net/v1"

    def __init__(self, api_key: str | None = None, auth_token: str | None = None):
        """Initialize the client.

        Args:
            api_key: API key in format `sk-...` (uses x-api-key header).
            auth_token: JWT token in format `io-v2-...` (uses Authorization header).
                        Falls back to settings.IO_NET_AUTH_TOKEN if not provided.
        """
        # Determine which credential to use
        self.api_key = api_key or settings.IO_NET_API_KEY
        self.auth_token = auth_token or settings.IO_NET_AUTH_TOKEN

        # Build headers based on available credentials
        # VMaaS (GPU leasing) uses x-api-key header for both API keys (sk-...) and JWT tokens (io-v2-...)
        # Intelligence API uses Authorization: Bearer for JWT tokens
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        elif self.auth_token:
            headers["x-api-key"] = self.auth_token
        else:
            raise ValueError(
                "No io.net credentials configured. "
                "Set IO_NET_API_KEY (sk-...) or IO_NET_AUTH_TOKEN (io-v2-...) in .env"
            )

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    # =========================================================================
    # VMaaS — GPU Cluster Management
    # =========================================================================

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def list_gpus(self, filters: Optional[HardwareFilter] = None) -> List[GPUHardware]:
        """
        GET /vmaas/hardware
        List available GPU hardware for leasing.
        """
        params = filters.to_dict() if filters else {}
        response = await self._client.get("/vmaas/hardware", params=params)
        response.raise_for_status()
        data = response.json()
        return [GPUHardware.from_api(**h) for h in data.get("data", {}).get("hardware", [])]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def get_price(self, hardware_id: str, duration_hours: int, currency: str = "usdc") -> PriceResponse:
        """
        GET /vmaas/price
        Calculate the cost of a GPU cluster.
        """
        params = {
            "hardware_id": hardware_id,
            "duration": duration_hours,
            "currency": currency,
        }
        response = await self._client.get("/vmaas/price", params=params)
        response.raise_for_status()
        return PriceResponse(**response.json()["data"])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def deploy_cluster(self, hardware_id: str, duration_hours: int, replica_count: int = 1) -> DeployResponse:
        """
        POST /vmaas/deploy
        Provision a GPU cluster.
        """
        payload = {
            "hardware_id": hardware_id,
            "duration_hours": duration_hours,
            "replica_count": replica_count,
        }
        response = await self._client.post("/vmaas/deploy", json=payload)
        response.raise_for_status()
        return DeployResponse(**response.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def extend_cluster(self, deployment_id: str, additional_hours: int) -> Dict[str, Any]:
        """
        POST /vmaas/extend
        Extend the duration of a running cluster.
        """
        payload = {
            "deployment_id": deployment_id,
            "additional_hours": additional_hours,
        }
        response = await self._client.post("/vmaas/extend", json=payload)
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def destroy_cluster(self, deployment_id: str) -> Dict[str, Any]:
        """
        DELETE /vmaas/destroy
        Terminate a cluster early (kill-switch).
        """
        response = await self._client.delete(f"/vmaas/destroy/{deployment_id}")
        response.raise_for_status()
        return response.json()

    async def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        """
        GET /vmaas/status/{deployment_id}
        Query the status of a deployment.
        """
        response = await self._client.get(f"/vmaas/status/{deployment_id}")
        response.raise_for_status()
        return DeploymentStatus(**response.json()["data"])

    # =========================================================================
    # CaaS — Container Deployment
    # =========================================================================

    async def deploy_container(
        self,
        image: str,
        gpu_count: int = 1,
        env_vars: Optional[Dict[str, str]] = None,
        command: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        POST /caas/deploy
        Deploy a container on GPU infrastructure.
        """
        payload = {
            "image": image,
            "gpu_count": gpu_count,
            "env": env_vars or {},
            "command": command or [],
        }
        response = await self._client.post("/caas/deploy", json=payload)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # IO Intelligence — AI Agents & Inference
    # =========================================================================

    async def list_models(self, supports_attestation: bool = False) -> List[Dict[str, Any]]:
        """List available AI models."""
        url = f"{self.INTELLIGENCE_URL}/models"
        response = await self._client.get(url)
        response.raise_for_status()
        models = response.json().get("data", [])
        if supports_attestation:
            models = [m for m in models if m.get("supports_attestation")]
        return models

    async def chat_completion(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """
        POST /v1/chat/completions
        Run inference with a selected model.
        """
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = await self._client.post(
            f"{self.INTELLIGENCE_URL}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def get_attestation(self, model_id: str, nonce: str) -> Dict[str, Any]:
        """
        POST /private/attestation
        Get GPU attestation for verifiable inference.
        """
        payload = {"model_id": model_id, "nonce": nonce}
        response = await self._client.post(
            f"{self.INTELLIGENCE_URL}/private/attestation",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
