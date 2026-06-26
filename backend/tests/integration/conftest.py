"""Shared fixtures and mocks for integration tests.

Provides mock dependencies for FastAPI endpoints:
- MockAsyncSession (SQLAlchemy)
- MockRedis (redis.asyncio)
- MockEventStore (PostgresEventStore)
- MockAPIKeyRepository
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_db_session, get_redis
from app.core.auth import get_api_key_repository, validate_api_key
from app.domain.events.base import DomainEvent


# =============================================================================
# Mocks
# =============================================================================

class MockAsyncSession:
    """Mock for SQLAlchemy AsyncSession."""

    def __init__(self):
        self.execute = AsyncMock()
        self.begin = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __call__(self, *args, **kwargs):
        return self


class MockRedis:
    """Mock for redis.asyncio.Redis."""

    def __init__(self):
        self._store: Dict[str, str] = {}
        self.ping = AsyncMock(return_value=True)
        self.exists = AsyncMock(side_effect=self._mock_exists)
        self.get = AsyncMock(side_effect=self._mock_get)
        self.setex = AsyncMock(side_effect=self._mock_setex)
        self.hgetall = AsyncMock(return_value={})
        self.eval = AsyncMock(return_value=1)
        self.close = AsyncMock()

    def _mock_exists(self, key: str) -> bool:
        return key in self._store

    def _mock_get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def _mock_setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value


class MockEventStore:
    """Mock for PostgresEventStore."""

    def __init__(self):
        self._streams: Dict[str, List[DomainEvent]] = {}
        self.append_events = AsyncMock(side_effect=self._mock_append)
        self.load_stream = AsyncMock(side_effect=self._mock_load)
        self.load_stream_from_version = AsyncMock(return_value=[])

    def _mock_append(
        self, stream_id: str, events: List[DomainEvent],
        expected_version: Optional[int] = None,
    ) -> None:
        if stream_id not in self._streams:
            self._streams[stream_id] = []
        for event in events:
            event.version = len(self._streams[stream_id]) + 1
            self._streams[stream_id].append(event)

    def _mock_load(self, stream_id: str) -> List[DomainEvent]:
        return self._streams.get(stream_id, [])


class MockAPIKeyRepository:
    """Mock for APIKeyRepository."""

    def __init__(self):
        self._keys: Dict[str, tuple[str, str]] = {}  # key_id -> (agent_id, hashed_key)
        self._aggregates: Dict[str, Any] = {}
        self.get_key_hash = AsyncMock(side_effect=self._mock_get_key_hash)
        self.load_agent_keys = AsyncMock(side_effect=self._mock_load_agent_keys)
        self.save = AsyncMock()

    def _mock_get_key_hash(self, key_id: str) -> tuple[Optional[str], Optional[str]]:
        entry = self._keys.get(key_id)
        if entry:
            return entry
        return (None, None)

    def _mock_load_agent_keys(self, agent_id: str) -> Any:
        if agent_id not in self._aggregates:
            from app.domain.aggregates.api_key import APIKeyAggregate
            self._aggregates[agent_id] = APIKeyAggregate(agent_id)
        return self._aggregates[agent_id]

    def add_key(self, key_id: str, agent_id: str, hashed_key: str) -> None:
        self._keys[key_id] = (agent_id, hashed_key)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Fixture: mock AsyncSession."""
    return MockAsyncSession()


@pytest.fixture
def mock_redis():
    """Fixture: mock Redis."""
    return MockRedis()


@pytest.fixture
def mock_event_store():
    """Fixture: mock EventStore."""
    return MockEventStore()


@pytest.fixture
def mock_api_key_repo():
    """Fixture: mock APIKeyRepository."""
    return MockAPIKeyRepository()


@pytest.fixture
def client(mock_db, mock_redis, mock_api_key_repo):
    """Fixture: FastAPI TestClient with overridden dependencies.

    Overrides:
        get_db_session -> mock_db
        get_redis -> mock_redis
        get_api_key_repository -> mock_api_key_repo
        validate_api_key -> returns "test-agent" (bypasses auth)
    """
    async def _override_db():
        yield mock_db

    async def _override_redis():
        yield mock_redis

    async def _override_api_key_repo():
        return mock_api_key_repo

    async def _override_validate_api_key():
        return "test-agent"

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_redis] = _override_redis
    app.dependency_overrides[get_api_key_repository] = _override_api_key_repo
    app.dependency_overrides[validate_api_key] = _override_validate_api_key

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
