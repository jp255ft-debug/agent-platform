"""Integration tests for GPU leasing endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_gpu_handlers
from app.core.auth import validate_api_key
from app.infrastructure.depin.ionet_models import (
    GPUHardware, PriceResponse, DeployResponse,
)


@pytest.fixture
def mock_gpu_handlers():
    """Create mocked GPUHandlers for testing."""
    with patch("app.application.handlers.gpu_handlers.GPUHandlers") as mock:
        handlers = AsyncMock()
        yield handlers


@pytest.fixture(autouse=True)
def override_auth():
    """Override authentication to return a mock agent_id."""
    app.dependency_overrides[validate_api_key] = lambda: "agent-test-123"
    yield
    # Clean up only if still present
    if validate_api_key in app.dependency_overrides:
        del app.dependency_overrides[validate_api_key]


@pytest.fixture
def client(mock_gpu_handlers):
    """Create TestClient with mocked GPU handlers."""
    app.dependency_overrides[get_gpu_handlers] = lambda: mock_gpu_handlers
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


GPU_HARDWARE_RESPONSE = [
    {
        "id": "gpu-1",
        "model": "RTX 4090",
        "gpu_count": 2,
        "vram_gb": 24,
        "total_vram_gb": 48,
        "price_per_hour_usdc": 1.50,
        "location": "US-East",
        "is_available": True,
        "vcpu": 16,
        "memory_gb": 64,
        "storage_gb": 500,
    },
    {
        "id": "gpu-2",
        "model": "A100",
        "gpu_count": 1,
        "vram_gb": 80,
        "total_vram_gb": 80,
        "price_per_hour_usdc": 3.00,
        "location": "US-West",
        "is_available": True,
        "vcpu": 32,
        "memory_gb": 128,
        "storage_gb": 1000,
    },
]


class TestListHardware:
    def test_list_hardware_success(self, client, mock_gpu_handlers):
        mock_gpu_handlers.list_available_gpus.return_value = GPU_HARDWARE_RESPONSE

        response = client.get("/api/v1/gpu/hardware")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "gpu-1"
        assert data[0]["model"] == "RTX 4090"
        assert data[0]["price_per_hour_usdc"] == 1.50
        assert data[1]["id"] == "gpu-2"

    def test_list_hardware_with_filters(self, client, mock_gpu_handlers):
        mock_gpu_handlers.list_available_gpus.return_value = [GPU_HARDWARE_RESPONSE[0]]

        response = client.get(
            "/api/v1/gpu/hardware",
            params={"search": "RTX", "min_vram": 16, "max_price": 2.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["model"] == "RTX 4090"

        mock_gpu_handlers.list_available_gpus.assert_called_once_with(
            search="RTX", min_vram=16, max_price=2.0,
        )

    def test_list_hardware_empty(self, client, mock_gpu_handlers):
        mock_gpu_handlers.list_available_gpus.return_value = []

        response = client.get("/api/v1/gpu/hardware")

        assert response.status_code == 200
        assert response.json() == []


class TestRequestLease:
    def test_request_lease_success(self, client, mock_gpu_handlers):
        mock_gpu_handlers.request_lease.return_value = {
            "lease_id": "lease-123",
            "deployment_id": "dep-123",
            "status": "provisioning",
            "total_cost_usdc": 50.0,
            "ionet_fee_usdc": 5.0,
            "expires_at": "2026-06-21T20:00:00+00:00",
        }

        response = client.post(
            "/api/v1/gpu/lease",
            json={
                "hardware_id": "gpu-1",
                "duration_hours": 4,
                "gpu_count": 2,
                "max_budget_usdc": 100.0,
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["lease_id"] == "lease-123"
        assert data["status"] == "provisioning"
        assert data["total_cost_usdc"] == 50.0

    def test_request_lease_minimal(self, client, mock_gpu_handlers):
        mock_gpu_handlers.request_lease.return_value = {
            "lease_id": "lease-456",
            "deployment_id": "dep-456",
            "status": "provisioning",
            "total_cost_usdc": 25.0,
            "ionet_fee_usdc": 2.5,
            "expires_at": None,
        }

        response = client.post(
            "/api/v1/gpu/lease",
            json={
                "hardware_id": "gpu-1",
                "duration_hours": 2,
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["lease_id"] == "lease-456"

    def test_request_lease_budget_exceeded(self, client, mock_gpu_handlers):
        mock_gpu_handlers.request_lease.side_effect = ValueError(
            "Budget exceeded: 100.0 > 50.0"
        )

        response = client.post(
            "/api/v1/gpu/lease",
            json={
                "hardware_id": "gpu-1",
                "duration_hours": 10,
                "max_budget_usdc": 50.0,
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 400

    def test_request_lease_invalid_duration(self, client, mock_gpu_handlers):
        response = client.post(
            "/api/v1/gpu/lease",
            json={
                "hardware_id": "gpu-1",
                "duration_hours": -1,
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 422  # Validation error


class TestGetLease:
    def test_get_lease_success(self, client, mock_gpu_handlers):
        mock_gpu_handlers.get_lease.return_value = {
            "lease_id": "lease-123",
            "status": "active",
            "gpu_model": "RTX 4090",
            "gpu_count": 2,
            "duration_hours": 4,
            "deployment_id": "dep-123",
            "total_cost_usdc": 50.0,
            "ionet_fee_usdc": 5.0,
            "created_at": "2026-06-21T12:00:00+00:00",
            "activated_at": "2026-06-21T12:05:00+00:00",
            "expires_at": "2026-06-21T16:00:00+00:00",
        }

        response = client.get(
            "/api/v1/gpu/leases/lease-123",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["lease_id"] == "lease-123"
        assert data["status"] == "active"
        assert data["gpu_model"] == "RTX 4090"

    def test_get_lease_not_found(self, client, mock_gpu_handlers):
        mock_gpu_handlers.get_lease.side_effect = ValueError(
            "Lease lease-999 not found"
        )

        response = client.get(
            "/api/v1/gpu/leases/lease-999",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 404

    def test_get_lease_unauthorized(self, client, mock_gpu_handlers):
        mock_gpu_handlers.get_lease.side_effect = ValueError(
            "Agent does not own this lease"
        )

        response = client.get(
            "/api/v1/gpu/leases/lease-123",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 403


class TestExtendLease:
    def test_extend_lease_success(self, client, mock_gpu_handlers):
        mock_gpu_handlers.extend_lease.return_value = {
            "lease_id": "lease-123",
            "status": "extending",
            "new_expires_at": "2026-06-21T20:00:00+00:00",
            "new_duration_hours": 8,
        }

        response = client.post(
            "/api/v1/gpu/leases/lease-123/extend",
            json={"additional_hours": 4},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["new_duration_hours"] == 8

    def test_extend_lease_not_found(self, client, mock_gpu_handlers):
        mock_gpu_handlers.extend_lease.side_effect = ValueError(
            "Lease lease-999 not found"
        )

        response = client.post(
            "/api/v1/gpu/leases/lease-999/extend",
            json={"additional_hours": 2},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 404

    def test_extend_lease_invalid_hours(self, client, mock_gpu_handlers):
        response = client.post(
            "/api/v1/gpu/leases/lease-123/extend",
            json={"additional_hours": 0},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 422


class TestTerminateLease:
    def test_terminate_lease_success(self, client, mock_gpu_handlers):
        mock_gpu_handlers.terminate_lease.return_value = None

        response = client.delete(
            "/api/v1/gpu/leases/lease-123",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 204

    def test_terminate_lease_not_found(self, client, mock_gpu_handlers):
        mock_gpu_handlers.terminate_lease.side_effect = ValueError(
            "Lease lease-999 not found"
        )

        response = client.delete(
            "/api/v1/gpu/leases/lease-999",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 404

    def test_terminate_lease_unauthorized(self, client, mock_gpu_handlers):
        mock_gpu_handlers.terminate_lease.side_effect = ValueError(
            "Agent does not own this lease"
        )

        response = client.delete(
            "/api/v1/gpu/leases/lease-123",
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 403
