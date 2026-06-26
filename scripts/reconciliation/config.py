"""Configuration and constants for reconciliation scripts."""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class ReconciliationConfig:
    """Configuration for reconciliation processes.

    Environment variables can override defaults:
        RPC_URL_BASE: Base L2 RPC endpoint
        PAYMENT_VERIFIER_ADDRESS: Deployed PaymentVerifier contract address
        AGENT_DELEGATION_ADDRESS: Deployed AgentDelegation contract address
        DATABASE_URL: PostgreSQL connection string
        RECONCILIATION_ALERT_WEBHOOK: Slack/Discord webhook for alerts
    """

    # Blockchain
    rpc_url: str = field(
        default_factory=lambda: os.getenv("RPC_URL_BASE", "https://sepolia.base.org")
    )
    payment_verifier_address: Optional[str] = field(
        default_factory=lambda: os.getenv("PAYMENT_VERIFIER_ADDRESS")
    )
    agent_delegation_address: Optional[str] = field(
        default_factory=lambda: os.getenv("AGENT_DELEGATION_ADDRESS")
    )

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://agent:agent@localhost:5432/agent_platform",
        )
    )

    # Alerting
    alert_webhook: Optional[str] = field(
        default_factory=lambda: os.getenv("RECONCILIATION_ALERT_WEBHOOK")
    )

    # Thresholds
    max_discrepancy_rate: float = 0.001  # 0.1% max discrepancy
    max_block_lag: int = 10  # Max blocks behind before alert
    reconciliation_window_hours: int = 24  # Lookback window
    latency_buffer_blocks: int = 3  # Buffer de latência para evitar falsos positivos em forks/reorgs

    # Execution intervals (in seconds)
    payment_interval: int = 3600  # 1 hour
    delegation_interval: int = 21600  # 6 hours
    state_channel_interval: int = 43200  # 12 hours


# Default instance
config = ReconciliationConfig()
