"""Invoice schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional


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
    invoices: List[InvoiceResponse]
    total: int
