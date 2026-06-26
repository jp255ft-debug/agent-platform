"""Invoice management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.invoices import InvoiceListResponse, InvoiceResponse
from app.application.commands.settle_invoice import SettleInvoiceCommand
from app.application.handlers.command_handlers import CommandHandlers
from app.core.dependencies import get_db_session
from app.core.exceptions import (
    DomainError,
    InvoiceAlreadySettledError,
    InvoiceNotFoundError,
)
from app.infrastructure.db.repositories.event_store import PostgresEventStore

router = APIRouter()


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get invoice details by ID."""
    event_store = PostgresEventStore(db)
    events = await event_store.load_stream(invoice_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    from app.domain.aggregates.invoice import InvoiceAggregate
    invoice = InvoiceAggregate(invoice_id)
    for event in events:
        invoice._apply(event)

    return InvoiceResponse(
        invoice_id=invoice.invoice_id,
        agent_id=invoice.agent_id or "",
        amount=invoice.amount,
        status=invoice.status,
        due_date=invoice.due_date or "",
        version=invoice.version,
    )


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    agent_id: str | None = None,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List invoices with optional filtering."""
    query = "SELECT DISTINCT stream_id FROM events WHERE stream_id LIKE 'invoice:%'"
    params = {}

    if agent_id:
        query += " AND data->>'agent_id' = :agent_id"
        params["agent_id"] = agent_id

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    invoices = []
    event_store = PostgresEventStore(db)
    from app.domain.aggregates.invoice import InvoiceAggregate

    for (stream_id,) in rows:
        events = await event_store.load_stream(stream_id)
        if events:
            invoice = InvoiceAggregate(stream_id)
            for event in events:
                invoice._apply(event)
            if status_filter and invoice.status != status_filter:
                continue
            invoices.append(InvoiceResponse(
                invoice_id=invoice.invoice_id,
                agent_id=invoice.agent_id or "",
                amount=invoice.amount,
                status=invoice.status,
                due_date=invoice.due_date or "",
                version=invoice.version,
            ))

    return InvoiceListResponse(invoices=invoices, total=len(invoices))


@router.post("/{invoice_id}/settle", response_model=InvoiceResponse)
async def settle_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Settle an invoice."""
    event_store = PostgresEventStore(db)
    handlers = CommandHandlers(event_store)
    command = SettleInvoiceCommand(invoice_id=invoice_id, agent_id="")
    try:
        await handlers.handle_settle_invoice(command)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except InvoiceAlreadySettledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.to_dict())
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())

    return await get_invoice(invoice_id, db)
