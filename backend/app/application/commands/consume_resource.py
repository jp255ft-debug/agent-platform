from dataclasses import dataclass

@dataclass
class ConsumeResourceCommand:
    agent_id: str
    resource_type: str
    amount: int
    x402_payment: dict
    idempotency_key: str | None = None
