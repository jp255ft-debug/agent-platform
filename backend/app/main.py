"""Agent Platform - Main Application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.dependencies import redis_client, engine
from app.api.v1.endpoints import agents, consume, invoices, health
from app.api.v1.middleware import RateLimitMiddleware
from app.api.websocket.event_handler import WebSocketEventHandler, manager
from app.infrastructure.messaging.kafka_producer import KafkaEventProducer

# Setup logging
setup_logging(settings.DEBUG)
logger = logging.getLogger(__name__)

# Global services
kafka_producer = KafkaEventProducer()
ws_event_handler = WebSocketEventHandler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("Starting Agent Platform API...")

    # Initialize Redis
    global redis_client
    from redis.asyncio import Redis
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis connection established")

    # Initialize Kafka producer
    try:
        await kafka_producer.start()
        logger.info("Kafka producer started")
    except Exception as e:
        logger.warning("Kafka not available: %s", str(e))

    yield

    # Shutdown
    logger.info("Shutting down Agent Platform API...")

    # Close Redis
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

    # Close Kafka
    try:
        await kafka_producer.stop()
        logger.info("Kafka producer stopped")
    except Exception:
        pass

    # Close database engine
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, max_requests=100, window=60)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(consume.router, prefix="/api/v1/consume", tags=["consume"])
app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["invoices"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming."""
    await ws_event_handler.handle_connection(websocket)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
