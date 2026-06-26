"""Integration tests for invoice management endpoints.

Tests:
    GET  /api/v1/invoices/{invoice_id} — Get invoice details
    GET  /api/v1/invoices — List invoices
    POST /api/v1/invoices/{invoice_id}/settle — Settle an invoice
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestGetInvoice:
    """Tests for GET /api/v1/invoices/{invoice_id}."""

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    def test_get_invoice_found(self, mock_store_cls, client: TestClient):
        """Should return invoice details when invoice exists."""
        from app.domain.events.payment_events import InvoiceGenerated

        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[
            InvoiceGenerated(
                invoice_id="inv-found",
                agent_id="agent-123",
                amount=100,
                due_date="2026-07-01T00:00:00Z",
            ),
        ])

        response = client.get("/api/v1/invoices/inv-found")
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_id"] == "inv-found"
        assert data["agent_id"] == "agent-123"
        assert data["amount"] == 100.0

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    def test_get_invoice_not_found(self, mock_store_cls, client: TestClient):
        """Should return 404 when invoice does not exist."""
        mock_store = mock_store_cls.return_value
        mock_store.load_stream = AsyncMock(return_value=[])

        response = client.get("/api/v1/invoices/non-existent-invoice")
        assert response.status_code == 404


class TestListInvoices:
    """Tests for GET /api/v1/invoices."""

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    def test_list_invoices_empty(self, mock_store_cls, client: TestClient, mock_db):
        """Should return empty list when no invoices exist."""
        # Configure mock_db.execute to return empty result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/invoices")
        assert response.status_code == 200
        data = response.json()
        assert data["invoices"] == []
        assert data["total"] == 0

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    def test_list_invoices_with_agent_filter(self, mock_store_cls, client: TestClient, mock_db):
        """Should filter invoices by agent_id."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/invoices?agent_id=agent-123")
        assert response.status_code == 200
        data = response.json()
        assert data["invoices"] == []

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    def test_list_invoices_with_status_filter(self, mock_store_cls, client: TestClient, mock_db):
        """Should filter invoices by status."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/invoices?status_filter=pending")
        assert response.status_code == 200
        data = response.json()
        assert data["invoices"] == []


class TestSettleInvoice:
    """Tests for POST /api/v1/invoices/{invoice_id}/settle."""

    @patch("app.api.v1.endpoints.invoices.PostgresEventStore")
    @patch("app.api.v1.endpoints.invoices.CommandHandlers")
    def test_settle_invoice_not_found(self, mock_handlers_cls, mock_store_cls, client: TestClient):
        """Should return 404 when settling non-existent invoice."""
        from app.core.exceptions import InvoiceNotFoundError

        mock_handlers = mock_handlers_cls.return_value
        mock_handlers.handle_settle_invoice = AsyncMock(
            side_effect=InvoiceNotFoundError("non-existent")
        )

        response = client.post("/api/v1/invoices/non-existent/settle")
        assert response.status_code == 404
