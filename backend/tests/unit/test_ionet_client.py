"""Unit tests for IonetClient with mocked HTTP responses."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.infrastructure.depin.ionet_client import IonetClient
from app.infrastructure.depin.ionet_models import (
    GPUHardware, PriceResponse, DeployResponse, DeploymentStatus, HardwareFilter,
)


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings to avoid real credentials."""
    with patch("app.infrastructure.depin.ionet_client.settings") as mock_settings:
        mock_settings.IO_NET_API_KEY = ""
        mock_settings.IO_NET_AUTH_TOKEN = ""
        yield mock_settings


@pytest.fixture
def mock_client():
    """Create an IonetClient with a mocked httpx.AsyncClient."""
    with patch("app.infrastructure.depin.ionet_client.httpx.AsyncClient") as mock_httpx:
        mock_instance = MagicMock()
        mock_httpx.return_value = mock_instance
        client = IonetClient(api_key="sk-test-key")
        client._client = mock_instance
        yield client


class TestIonetClientInit:
    def test_init_with_api_key(self):
        with patch("app.infrastructure.depin.ionet_client.httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value = mock_instance
            client = IonetClient(api_key="sk-test-key")
            assert client.api_key == "sk-test-key"
            assert client.auth_token == ""  # empty string from mock_settings
            mock_httpx.assert_called_once()
            call_kwargs = mock_httpx.call_args.kwargs
            assert call_kwargs["headers"]["x-api-key"] == "sk-test-key"

    def test_init_with_auth_token(self):
        with patch("app.infrastructure.depin.ionet_client.httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value = mock_instance
            client = IonetClient(auth_token="io-v2-test-token")
            assert client.api_key == ""
            assert client.auth_token == "io-v2-test-token"
            mock_httpx.assert_called_once()
            call_kwargs = mock_httpx.call_args.kwargs
            # VMaaS uses x-api-key header for both API keys and JWT tokens
            assert call_kwargs["headers"]["x-api-key"] == "io-v2-test-token"

    def test_init_without_credentials_raises(self):
        with patch("app.infrastructure.depin.ionet_client.settings") as mock_settings:
            mock_settings.IO_NET_API_KEY = ""
            mock_settings.IO_NET_AUTH_TOKEN = ""
            with pytest.raises(ValueError, match="No io.net credentials configured"):
                IonetClient()


class TestListGPUs:
    @pytest.mark.asyncio
    async def test_list_gpus_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "hardware": [
                    {
                        "id": "gpu-1",
                        "name": "RTX 4090",
                        "num_cards": 2,
                        "supplier": "internal",
                        "sold_out": False,
                        "price": 1.50,
                        "vram_per_card": 24,
                        "location": "US-East",
                        "vcpu": 16,
                        "memory": 64,
                        "storage": 500,
                        "interconnect": "nvlink",
                        "nvlink": True,
                    },
                    {
                        "id": "gpu-2",
                        "name": "A100",
                        "num_cards": 1,
                        "supplier": "external",
                        "sold_out": True,
                        "price": 3.00,
                        "vram_per_card": 80,
                        "location": "US-West",
                        "vcpu": 32,
                        "memory": 128,
                        "storage": 1000,
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        gpus = await mock_client.list_gpus()

        assert len(gpus) == 2
        assert isinstance(gpus[0], GPUHardware)
        assert gpus[0].id == "gpu-1"
        assert gpus[0].name == "RTX 4090"
        assert gpus[0].num_cards == 2
        assert gpus[0].total_vram_gb == 48  # 24 * 2
        assert gpus[0].is_available is True
        assert gpus[0].nvlink is True

        assert gpus[1].id == "gpu-2"
        assert gpus[1].is_available is False  # sold_out = True

        mock_client._client.get.assert_called_once_with("/vmaas/hardware", params={})

    @pytest.mark.asyncio
    async def test_list_gpus_with_filters(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"hardware": []}}
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        hw_filter = HardwareFilter(
            search="RTX",
            regions=["US-East", "EU-West"],
            min_gpu_memory=16,
            supplier="internal",
        )
        await mock_client.list_gpus(hw_filter)

        mock_client._client.get.assert_called_once()
        params = mock_client._client.get.call_args.kwargs["params"]
        assert params["search"] == "RTX"
        assert params["regions"] == "US-East,EU-West"
        assert params["min_gpu_memory"] == "16"
        assert params["supplier"] == "internal"

    @pytest.mark.asyncio
    async def test_list_gpus_empty_response(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"hardware": []}}
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        gpus = await mock_client.list_gpus()
        assert gpus == []


class TestGetPrice:
    @pytest.mark.asyncio
    async def test_get_price_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "total_cost_usdc": 50.0,
                "ionet_fee": 5.0,
                "ionet_fee_percent": 10.0,
                "replica_count": 1,
                "gpus_per_vm": 2,
                "available_replica_count": [1, 2, 4],
                "discount": 0.0,
                "currency_conversion_fee": 0.0,
                "currency_conversion_fee_percent": 0.0,
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        price = await mock_client.get_price(hardware_id="gpu-1", duration_hours=4)

        assert isinstance(price, PriceResponse)
        assert price.total_cost_usdc == 50.0
        assert price.ionet_fee == 5.0
        assert price.ionet_fee_percent == 10.0
        assert price.replica_count == 1
        assert price.gpus_per_vm == 2
        assert price.available_replica_count == [1, 2, 4]

        mock_client._client.get.assert_called_once_with(
            "/vmaas/price",
            params={"hardware_id": "gpu-1", "duration": 4, "currency": "usdc"},
        )


class TestDeployCluster:
    @pytest.mark.asyncio
    async def test_deploy_cluster_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "deployment_id": "dep-123",
            "status": "provisioning",
            "message": "Cluster provisioning started",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)

        deploy = await mock_client.deploy_cluster(
            hardware_id="gpu-1",
            duration_hours=4,
            replica_count=2,
        )

        assert isinstance(deploy, DeployResponse)
        assert deploy.deployment_id == "dep-123"
        assert deploy.status == "provisioning"
        assert deploy.message == "Cluster provisioning started"

        mock_client._client.post.assert_called_once_with(
            "/vmaas/deploy",
            json={"hardware_id": "gpu-1", "duration_hours": 4, "replica_count": 2},
        )


class TestExtendCluster:
    @pytest.mark.asyncio
    async def test_extend_cluster_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "deployment_id": "dep-123",
            "new_expires_at": "2026-06-22T15:00:00Z",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.extend_cluster(
            deployment_id="dep-123",
            additional_hours=4,
        )

        assert result["deployment_id"] == "dep-123"
        assert "new_expires_at" in result

        mock_client._client.post.assert_called_once_with(
            "/vmaas/extend",
            json={"deployment_id": "dep-123", "additional_hours": 4},
        )


class TestDestroyCluster:
    @pytest.mark.asyncio
    async def test_destroy_cluster_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "terminated"}
        mock_response.raise_for_status = MagicMock()
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.destroy_cluster(deployment_id="dep-123")

        assert result["status"] == "terminated"
        mock_client._client.delete.assert_called_once_with("/vmaas/destroy/dep-123")


class TestGetDeploymentStatus:
    @pytest.mark.asyncio
    async def test_get_deployment_status_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "deployment_id": "dep-123",
                "status": "running",
                "hardware_id": "gpu-1",
                "replica_count": 2,
                "created_at": "2026-06-21T12:00:00Z",
                "expires_at": "2026-06-21T16:00:00Z",
                "gpu_model": "RTX 4090",
                "gpu_count": 4,
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        status = await mock_client.get_deployment_status(deployment_id="dep-123")

        assert isinstance(status, DeploymentStatus)
        assert status.deployment_id == "dep-123"
        assert status.status == "running"
        assert status.gpu_model == "RTX 4090"
        assert status.gpu_count == 4

        mock_client._client.get.assert_called_once_with("/vmaas/status/dep-123")


class TestDeployContainer:
    @pytest.mark.asyncio
    async def test_deploy_container_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "deployment_id": "container-123",
            "status": "running",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.deploy_container(
            image="nvidia/cuda:12.0",
            gpu_count=2,
            env_vars={"MODEL": "llama2"},
            command=["python", "train.py"],
        )

        assert result["deployment_id"] == "container-123"

        mock_client._client.post.assert_called_once_with(
            "/caas/deploy",
            json={
                "image": "nvidia/cuda:12.0",
                "gpu_count": 2,
                "env": {"MODEL": "llama2"},
                "command": ["python", "train.py"],
            },
        )


class TestListModels:
    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "model-1", "name": "Llama 2", "supports_attestation": True},
                {"id": "model-2", "name": "GPT-4", "supports_attestation": False},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        models = await mock_client.list_models()

        assert len(models) == 2
        assert models[0]["id"] == "model-1"

    @pytest.mark.asyncio
    async def test_list_models_with_attestation_filter(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "model-1", "name": "Llama 2", "supports_attestation": True},
                {"id": "model-2", "name": "GPT-4", "supports_attestation": False},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get = AsyncMock(return_value=mock_response)

        models = await mock_client.list_models(supports_attestation=True)

        assert len(models) == 1
        assert models[0]["id"] == "model-1"


class TestChatCompletion:
    @pytest.mark.asyncio
    async def test_chat_completion_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chat-123",
            "choices": [{"message": {"content": "Hello!"}}],
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.chat_completion(
            model_id="model-1",
            messages=[{"role": "user", "content": "Say hello"}],
        )

        assert result["id"] == "chat-123"


class TestGetAttestation:
    @pytest.mark.asyncio
    async def test_get_attestation_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "attestation": "0xabc123",
            "model_id": "model-1",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.get_attestation(
            model_id="model-1",
            nonce="nonce-123",
        )

        assert result["attestation"] == "0xabc123"


class TestHardwareFilter:
    def test_to_dict_empty(self):
        hw_filter = HardwareFilter()
        assert hw_filter.to_dict() == {}

    def test_to_dict_all_fields(self):
        hw_filter = HardwareFilter(
            search="RTX",
            regions=["US-East", "EU-West"],
            min_gpu_memory=16,
            max_gpu_memory=80,
            min_vcpu=8,
            max_vcpu=64,
            min_memory=32,
            max_memory=256,
            min_storage=100,
            max_storage=2000,
            supplier="internal",
        )
        result = hw_filter.to_dict()
        assert result["search"] == "RTX"
        assert result["regions"] == "US-East,EU-West"
        assert result["min_gpu_memory"] == "16"
        assert result["max_gpu_memory"] == "80"
        assert result["min_vcpu"] == "8"
        assert result["max_vcpu"] == "64"
        assert result["min_memory"] == "32"
        assert result["max_memory"] == "256"
        assert result["min_storage"] == "100"
        assert result["max_storage"] == "2000"
        assert result["supplier"] == "internal"

    def test_to_dict_partial(self):
        hw_filter = HardwareFilter(search="A100", min_gpu_memory=40)
        result = hw_filter.to_dict()
        assert result["search"] == "A100"
        assert result["min_gpu_memory"] == "40"
        assert "regions" not in result
        assert "max_gpu_memory" not in result
