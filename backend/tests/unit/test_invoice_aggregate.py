"""Unit tests for InvoiceAggregate."""
import pytest

from app.domain.aggregates.invoice import InvoiceAggregate
from app.domain.events.payment_events import InvoiceGenerated, InvoicePaid


class TestInvoiceGenerate:
    def test_generate_creates_pending_invoice(self):
        invoice = InvoiceAggregate.generate(
            invoice_id="inv-1",
            agent_id="agent-1",
            amount=100_000,
            due_date="2026-07-01",
        )
        assert invoice.invoice_id == "inv-1"
        assert invoice.agent_id == "agent-1"
        assert invoice.amount == 100_000
        assert invoice.due_date == "2026-07-01"
        assert invoice.status == "pending"

    def test_generate_emits_invoice_generated_event(self):
        invoice = InvoiceAggregate.generate(
            invoice_id="inv-1",
            agent_id="agent-1",
            amount=100_000,
            due_date="2026-07-01",
        )
        changes = invoice.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], InvoiceGenerated)
        assert changes[0].data["agent_id"] == "agent-1"
        assert changes[0].data["amount"] == 100_000
        assert changes[0].data["due_date"] == "2026-07-01"


class TestInvoicePay:
    def test_pay_sets_status_to_paid(self):
        invoice = InvoiceAggregate.generate("inv-1", "agent-1", 100_000, "2026-07-01")
        invoice.clear_changes()
        invoice.pay(tx_hash="0xabc")
        assert invoice.status == "paid"

    def test_pay_emits_invoice_paid_event(self):
        invoice = InvoiceAggregate.generate("inv-1", "agent-1", 100_000, "2026-07-01")
        invoice.clear_changes()
        invoice.pay(tx_hash="0xabc")
        changes = invoice.get_changes()
        assert len(changes) == 1
        assert isinstance(changes[0], InvoicePaid)
        assert changes[0].data["tx_hash"] == "0xabc"


class TestInvoiceEventSourcing:
    def test_rebuild_from_events(self):
        invoice = InvoiceAggregate(invoice_id="inv-1")
        event1 = InvoiceGenerated(
            "inv-1", "agent-1", 100_000, "2026-07-01",
        )
        event2 = InvoicePaid(
            "inv-1", "0xabc",
        )
        invoice._apply(event1)
        invoice._apply(event2)
        assert invoice.agent_id == "agent-1"
        assert invoice.amount == 100_000
        assert invoice.due_date == "2026-07-01"
        assert invoice.status == "paid"
        assert invoice.version == 2

    def test_get_changes_returns_copy(self):
        invoice = InvoiceAggregate.generate("inv-1", "agent-1", 100_000, "2026-07-01")
        changes = invoice.get_changes()
        assert len(changes) == 1
        changes.clear()
        assert len(invoice.get_changes()) == 1

    def test_clear_changes_empties_list(self):
        invoice = InvoiceAggregate.generate("inv-1", "agent-1", 100_000, "2026-07-01")
        invoice.clear_changes()
        assert len(invoice.get_changes()) == 0

    def test_version_increments(self):
        invoice = InvoiceAggregate.generate("inv-1", "agent-1", 100_000, "2026-07-01")
        assert invoice.version == 1
        invoice.pay(tx_hash="0xabc")
        assert invoice.version == 2
