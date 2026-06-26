"""FastAPI dependencies."""
from collections.abc import AsyncGenerator

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.APP_DEBUG)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
redis_client: Redis | None = None

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_redis() -> AsyncGenerator[Redis, None]:
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis_client
    finally:
        pass


# ─── GPU / io.net Dependencies ────────────────────────────────────────────────

from app.application.handlers.gpu_handlers import GPUHandlers
from app.infrastructure.db.repositories.event_store import PostgresEventStore
from app.infrastructure.depin.ionet_client import IonetClient
from app.infrastructure.depin.ionet_simulator import IonetSimulator

# Singleton: IonetSimulator mantém deployments em memória entre requisições
_simulator_instance: IonetSimulator | None = None


def _create_ionet_client():
    """
    Factory: returns IonetSimulator if IO_NET_SIMULATOR=true or no credentials,
    otherwise returns real IonetClient.

    IonetSimulator é singleton para preservar o estado dos deployments
    entre requisições (necessário para o kill-switch funcionar).
    """
    global _simulator_instance
    if settings.IO_NET_SIMULATOR:
        if _simulator_instance is None:
            _simulator_instance = IonetSimulator()
        return _simulator_instance
    if not settings.IO_NET_API_KEY and not settings.IO_NET_AUTH_TOKEN:
        if _simulator_instance is None:
            _simulator_instance = IonetSimulator()
        return _simulator_instance
    return IonetClient()


async def get_event_store(
    db: AsyncSession = Depends(get_db_session),
) -> PostgresEventStore:
    """Dependency: returns PostgresEventStore instance."""
    return PostgresEventStore(db)


async def get_gpu_handlers(
    db: AsyncSession = Depends(get_db_session),
) -> GPUHandlers:
    """Dependency: returns GPUHandlers with event store and io.net client."""
    event_store = PostgresEventStore(db)
    ionet_client = _create_ionet_client()
    return GPUHandlers(event_store=event_store, ionet_client=ionet_client)
