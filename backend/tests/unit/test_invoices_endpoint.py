"""Unit tests for the invoices endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


class TestGetInvoice:
    """Tests for GET /api/v1/invoices/{invoice_id}"""

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    async def test_get_invoice_found(self, mock_store_cls, mock_db_session):
        """Test getting an invoice that exists."""
        from app.api.v1.endpoints.invoices import get_invoice
        from app.domain.events.payment_events import InvoiceGenerated

        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(
            return_value=[
                InvoiceGenerated(
                    invoice_id="inv-123",
                    agent_id="agent-123",
                    amount=1000,
                    due_date="2026-07-21",
                )
            ]
        )
        mock_store_cls.return_value = mock_store

        response = await get_invoice("inv-123", mock_db_session)
        assert response.invoice_id == "inv-123"
        assert response.agent_id == "agent-123"
        assert response.amount == 1000
        assert response.status == "pending"

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    async def test_get_invoice_not_found(self, mock_store_cls, mock_db_session):
        """Test getting an invoice that does not exist."""
        from app.api.v1.endpoints.invoices import get_invoice

        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(return_value=[])
        mock_store_cls.return_value = mock_store

        with pytest.raises(HTTPException) as exc:
            await get_invoice("inv-unknown", mock_db_session)
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


class TestListInvoices:
    """Tests for GET /api/v1/invoices"""

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    async def test_list_invoices_no_filter(self, mock_store_cls, mock_db_session):
        """Test listing all invoices."""
        from app.api.v1.endpoints.invoices import list_invoices
        from app.domain.events.payment_events import InvoiceGenerated

        # Mock DB result with stream IDs
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(
            return_value=[("invoice:inv-1",), ("invoice:inv-2",)]
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock event store returns events for each invoice
        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(
            side_effect=[
                [
                    InvoiceGenerated(
                        invoice_id="inv-1",
                        agent_id="agent-1",
                        amount=500,
                        due_date="2026-07-21",
                    )
                ],
                [
                    InvoiceGenerated(
                        invoice_id="inv-2",
                        agent_id="agent-2",
                        amount=1000,
                        due_date="2026-07-15",
                    )
                ],
            ]
        )
        mock_store_cls.return_value = mock_store

        response = await list_invoices(None, None, mock_db_session)
        assert response.total == 2
        assert len(response.invoices) == 2

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    async def test_list_invoices_with_agent_filter(
        self, mock_store_cls, mock_db_session
    ):
        """Test listing invoices filtered by agent_id."""
        from app.api.v1.endpoints.invoices import list_invoices
        from app.domain.events.payment_events import InvoiceGenerated

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(
            return_value=[("invoice:inv-1",)]
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(
            return_value=[
                InvoiceGenerated(
                    invoice_id="inv-1",
                    agent_id="agent-1",
                    amount=500,
                    due_date="2026-07-21",
                )
            ]
        )
        mock_store_cls.return_value = mock_store

        response = await list_invoices("agent-1", None, mock_db_session)
        assert response.total == 1
        assert response.invoices[0].agent_id == "agent-1"

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    async def test_list_invoices_with_status_filter(
        self, mock_store_cls, mock_db_session
    ):
        """Test listing invoices filtered by status."""
        from app.api.v1.endpoints.invoices import list_invoices
        from app.domain.events.payment_events import InvoiceGenerated, InvoicePaid

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(
            return_value=[("invoice:inv-1",), ("invoice:inv-2",)]
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_store = AsyncMock()
        mock_store.load_stream = AsyncMock(
            side_effect=[
                [
                    InvoiceGenerated(
                        invoice_id="inv-1",
                        agent_id="agent-1",
                        amount=500,
                        due_date="2026-07-21",
                    )
                ],
                [
                    InvoiceGenerated(
                        invoice_id="inv-2",
                        agent_id="agent-2",
                        amount=1000,
                        due_date="2026-07-15",
                    ),
                    InvoicePaid(invoice_id="inv-2", tx_hash="0xabc"),
                ],
            ]
        )
        mock_store_cls.return_value = mock_store

        response = await list_invoices(None, "paid", mock_db_session)
        assert response.total == 1
        assert response.invoices[0].status == "paid"

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    async def test_list_invoices_empty(self, mock_store_cls, mock_db_session):
        """Test listing invoices when none exist."""
        from app.api.v1.endpoints.invoices import list_invoices

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await list_invoices(None, None, mock_db_session)
        assert response.total == 0
        assert response.invoices == []


class TestSettleInvoice:
    """Tests for POST /api/v1/invoices/{invoice_id}/settle"""

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    @patch("app.api.v1.endpoints.invoices.CommandHandlers")
    async def test_settle_invoice_success(
        self, mock_handlers_cls, mock_store_cls, mock_db_session
    ):
        """Test settling an invoice successfully."""
        from app.api.v1.endpoints.invoices import settle_invoice

        mock_store = AsyncMock()
        mock_store_cls.return_value = mock_store

        mock_handlers = AsyncMock()
        mock_handlers.handle_settle_invoice = AsyncMock()
        mock_handlers_cls.return_value = mock_handlers

        # Mock get_invoice to return a response
        with patch(
            "app.api.v1.endpoints.invoices.get_invoice",
            new=AsyncMock(
                return_value=MagicMock(
                    invoice_id="inv-123",
                    agent_id="agent-123",
                    amount=1000,
                    status="settled",
                    due_date="2026-07-21",
                    version=2,
                )
            ),
        ):
            response = await settle_invoice("inv-123", mock_db_session)
            assert response.status == "settled"

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    @patch("app.api.v1.endpoints.invoices.CommandHandlers")
    async def test_settle_invoice_not_found(
        self, mock_handlers_cls, mock_store_cls, mock_db_session
    ):
        """Test settling a non-existent invoice."""
        from app.api.v1.endpoints.invoices import settle_invoice
        from app.core.exceptions import InvoiceNotFoundError

        mock_store = AsyncMock()
        mock_store_cls.return_value = mock_store

        mock_handlers = AsyncMock()
        mock_handlers.handle_settle_invoice = AsyncMock(
            side_effect=InvoiceNotFoundError("inv-unknown")
        )
        mock_handlers_cls.return_value = mock_handlers

        with pytest.raises(HTTPException) as exc:
            await settle_invoice("inv-unknown", mock_db_session)
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    @patch("app.api.v1.endpoints.invoices.CommandHandlers")
    async def test_settle_invoice_already_settled(
        self, mock_handlers_cls, mock_store_cls, mock_db_session
    ):
        """Test settling an already settled invoice."""
        from app.api.v1.endpoints.invoices import settle_invoice
        from app.core.exceptions import InvoiceAlreadySettledError

        mock_store = AsyncMock()
        mock_store_cls.return_value = mock_store

        mock_handlers = AsyncMock()
        mock_handlers.handle_settle_invoice = AsyncMock(
            side_effect=InvoiceAlreadySettledError("inv-123", "paid")
        )
        mock_handlers_cls.return_value = mock_handlers

        with pytest.raises(HTTPException) as exc:
            await settle_invoice("inv-123", mock_db_session)
        assert exc.value.status_code == status.HTTP_409_CONFLICT
