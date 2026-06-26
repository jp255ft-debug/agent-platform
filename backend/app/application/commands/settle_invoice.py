from dataclasses import dataclass


@dataclass
class SettleInvoiceCommand:
    invoice_id: str
    agent_id: str
