"""Invoice schemas."""

from pydantic import BaseModel


class InvoiceResponse(BaseModel):
    invoice_id: str
    agent_id: str
    amount: int
    status: str
    due_date: str
    version: int

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceResponse]
    total: int
