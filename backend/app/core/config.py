"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Agent Platform"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["*"]
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
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
