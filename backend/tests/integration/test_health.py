"""Integration tests for health check endpoint.

Tests:
    GET /health — verifies database and Redis connectivity
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test suite for GET /health."""

    def test_health_healthy(self, client: TestClient, mock_db, mock_redis):
        """Should return healthy when both DB and Redis respond."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"] == "healthy"
        assert data["services"]["redis"] == "healthy"
        assert "version" in data

    def test_health_db_unhealthy(self, client: TestClient, mock_db, mock_redis):
        """Should return degraded when database fails."""
        mock_db.execute.side_effect = Exception("DB connection failed")
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"] == "unhealthy"
        assert data["services"]["redis"] == "healthy"

    def test_health_redis_unhealthy(self, client: TestClient, mock_db, mock_redis):
        """Should return degraded when Redis fails."""
        mock_redis.ping.side_effect = Exception("Redis connection failed")
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"] == "healthy"
        assert data["services"]["redis"] == "unhealthy"

    def test_health_both_unhealthy(self, client: TestClient, mock_db, mock_redis):
        """Should return degraded when both services fail."""
        mock_db.execute.side_effect = Exception("DB connection failed")
        mock_redis.ping.side_effect = Exception("Redis connection failed")
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"] == "unhealthy"
        assert data["services"]["redis"] == "unhealthy"
