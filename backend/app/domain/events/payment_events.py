from app.domain.events.base import DomainEvent


class PaymentReceived(DomainEvent):
    def __init__(self, payment_id: str, sender: str, recipient: str, amount: int):
        super().__init__(aggregate_id=payment_id, data={
            "payment_id": payment_id, "sender": sender,
            "recipient": recipient, "amount": amount})

class PaymentVerified(DomainEvent):
    def __init__(self, payment_id: str, tx_hash: str, block_number: int):
        super().__init__(aggregate_id=payment_id, data={
            "payment_id": payment_id, "tx_hash": tx_hash, "block_number": block_number})

class PaymentFailed(DomainEvent):
    def __init__(self, payment_id: str, reason: str):
        super().__init__(aggregate_id=payment_id, data={"payment_id": payment_id, "reason": reason})

class InvoiceGenerated(DomainEvent):
    def __init__(self, invoice_id: str, agent_id: str, amount: int, due_date: str):
        super().__init__(aggregate_id=invoice_id, data={
            "invoice_id": invoice_id, "agent_id": agent_id,
            "amount": amount, "due_date": due_date})

class InvoicePaid(DomainEvent):
    def __init__(self, invoice_id: str, tx_hash: str):
        super().__init__(aggregate_id=invoice_id, data={
            "invoice_id": invoice_id, "tx_hash": tx_hash})

class PixPaymentReceived(DomainEvent):
    """Event emitted when a Pix payment is confirmed via webhook.

    Based on BUILD_GUIDE.md §16 — Camada 11: Integração com Sistema Financeiro Brasileiro.
    """
    def __init__(self, payment_id: str, qr_code_id: str, agent_id: str,
                 amount_brl: float, payer_name: str, payer_document: str,
                 paid_at: str):
        super().__init__(aggregate_id=payment_id, data={
            "payment_id": payment_id,
            "qr_code_id": qr_code_id,
            "agent_id": agent_id,
            "amount_brl": amount_brl,
            "payer_name": payer_name,
            "payer_document": payer_document,
            "paid_at": paid_at,
        })
