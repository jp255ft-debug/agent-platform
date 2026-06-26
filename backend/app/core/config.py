"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Agent Platform"
    VERSION: str = "0.1.0"
    APP_DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["*"]
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@postgres:5432/agent_platform"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    REDIS_URL: str = "redis://redis:6379/0"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_CONSUMER_GROUP: str = "agent-platform"
    RPC_URL_BASE: str = "https://sepolia.base.org"
    CONTRACT_DEPLOYER_KEY: str = ""
    AGENT_DELEGATION_ADDRESS: str = ""
    REPUTATION_SBT_ADDRESS: str = ""
    PAYMENT_VERIFIER_ADDRESS: str = ""
    TIMESCALEDB_URL: str = "postgresql+asyncpg://user:pass@timescaledb:5432/agent_analytics"
    PROMETHEUS_ENABLED: bool = True

    # ─── io.net DePIN ─────────────────────────────────────────────────────────
    IO_NET_API_KEY: str = ""
    IO_NET_AUTH_TOKEN: str = ""
    IO_NET_WEBHOOK_SECRET: str = ""
    IO_NET_SIMULATOR: bool = False

    # ─── Pix / Stark Bank ────────────────────────────────────────────────────
    STARK_BANK_API_KEY: str = ""
    STARK_BANK_ENVIRONMENT: str = "sandbox"
    STARK_BANK_WEBHOOK_URL: str = ""
    STARK_BANK_WEBHOOK_SECRET: str = ""

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

settings = Settings()
