
from app.domain.events.base import DomainEvent
from app.domain.events.payment_events import InvoiceGenerated, InvoicePaid


class InvoiceAggregate:
    def __init__(self, invoice_id: str):
        self.invoice_id: str = invoice_id
        self.agent_id: str | None = None
        self.amount: int = 0
        self.status: str = "pending"
        self.due_date: str | None = None
        self.version: int = 0
        self._changes: list[DomainEvent] = []

    @staticmethod
    def generate(invoice_id: str, agent_id: str, amount: int, due_date: str):
        invoice = InvoiceAggregate(invoice_id)
        event = InvoiceGenerated(invoice_id, agent_id, amount, due_date)
        invoice._apply(event)
        invoice._changes.append(event)
        return invoice

    def pay(self, tx_hash: str) -> None:
        event = InvoicePaid(self.invoice_id, tx_hash)
        self._apply(event)
        self._changes.append(event)

    def _apply(self, event: DomainEvent) -> None:
        if isinstance(event, InvoiceGenerated):
            self.agent_id = event.data["agent_id"]
            self.amount = event.data["amount"]
            self.due_date = event.data["due_date"]
            self.status = "pending"
        elif isinstance(event, InvoicePaid):
            self.status = "paid"
        self.version += 1

    def get_changes(self) -> list[DomainEvent]:
        return self._changes.copy()

    def clear_changes(self) -> None:
        self._changes.clear()
