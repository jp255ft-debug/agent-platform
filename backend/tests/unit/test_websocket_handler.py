"""Unit tests for WebSocket event handler and ConnectionManager."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from fastapi import WebSocket

from app.api.websocket.event_handler import ConnectionManager, WebSocketEventHandler, manager


class TestConnectionManager:
    """Test ConnectionManager class."""

    @pytest.fixture
    def conn_manager(self):
        return ConnectionManager()

    @pytest.fixture
    def mock_ws(self):
        ws = MagicMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock()
        return ws

    class TestConnect:
        async def test_connect_accepts_and_adds(self, conn_manager, mock_ws):
            await conn_manager.connect(mock_ws)

            mock_ws.accept.assert_awaited_once()
            assert mock_ws in conn_manager._connections

    class TestDisconnect:
        async def test_disconnect_removes_connection(self, conn_manager, mock_ws):
            conn_manager._connections.add(mock_ws)

            await conn_manager.disconnect(mock_ws)

            assert mock_ws not in conn_manager._connections

        async def test_disconnect_unknown_connection(self, conn_manager, mock_ws):
            # Should not raise
            await conn_manager.disconnect(mock_ws)

    class TestBroadcast:
        async def test_broadcast_sends_to_all(self, conn_manager):
            ws1 = MagicMock(spec=WebSocket)
            ws1.send_json = AsyncMock()
            ws2 = MagicMock(spec=WebSocket)
            ws2.send_json = AsyncMock()
            conn_manager._connections.update([ws1, ws2])

            await conn_manager.broadcast({"type": "test", "data": "hello"})

            ws1.send_json.assert_awaited_once_with({"type": "test", "data": "hello"})
            ws2.send_json.assert_awaited_once_with({"type": "test", "data": "hello"})

        async def test_broadcast_removes_dead_connections(self, conn_manager):
            ws1 = MagicMock(spec=WebSocket)
            ws1.send_json = AsyncMock()
            ws2 = MagicMock(spec=WebSocket)
            ws2.send_json = AsyncMock(side_effect=Exception("Connection closed"))
            conn_manager._connections.update([ws1, ws2])

            await conn_manager.broadcast({"type": "test"})

            # Dead connection should be removed
            assert ws1 in conn_manager._connections
            assert ws2 not in conn_manager._connections

        async def test_broadcast_empty_connections(self, conn_manager):
            # Should not raise
            await conn_manager.broadcast({"type": "test"})

    class TestSendToAgent:
        async def test_send_to_agent_broadcasts(self, conn_manager):
            ws = MagicMock(spec=WebSocket)
            ws.send_json = AsyncMock()
            conn_manager._connections.add(ws)

            await conn_manager.send_to_agent("agent_123", {"type": "agent_update"})

            ws.send_json.assert_awaited_once_with({"type": "agent_update"})


class TestWebSocketEventHandler:
    """Test WebSocketEventHandler class."""

    @pytest.fixture
    def handler(self):
        return WebSocketEventHandler()

    @pytest.fixture
    def mock_ws(self):
        ws = MagicMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock()
        return ws

    class TestHandleConnection:
        async def test_accepts_connection_and_handles_ping(self, handler, mock_ws):
            mock_ws.receive_text.side_effect = [
                json.dumps({"type": "ping"}),
                WebSocketDisconnect(),
            ]

            await handler.handle_connection(mock_ws)

            mock_ws.accept.assert_awaited_once()
            mock_ws.send_json.assert_any_call({"type": "pong"})

        async def test_handles_subscribe_message(self, handler, mock_ws):
            mock_ws.receive_text.side_effect = [
                json.dumps({"type": "subscribe", "channels": ["events", "alerts"]}),
                WebSocketDisconnect(),
            ]

            await handler.handle_connection(mock_ws)

            mock_ws.send_json.assert_any_call({
                "type": "subscribed",
                "channels": ["events", "alerts"],
            })

        async def test_handles_unknown_message_type(self, handler, mock_ws):
            mock_ws.receive_text.side_effect = [
                json.dumps({"type": "unknown_type"}),
                WebSocketDisconnect(),
            ]

            await handler.handle_connection(mock_ws)

            mock_ws.send_json.assert_any_call({
                "type": "error",
                "message": "Unknown message type: unknown_type",
            })

        async def test_handles_invalid_json(self, handler, mock_ws):
            mock_ws.receive_text.side_effect = [
                "not valid json",
                WebSocketDisconnect(),
            ]

            await handler.handle_connection(mock_ws)

            mock_ws.send_json.assert_any_call({
                "type": "error",
                "message": "Invalid JSON",
            })

        async def test_handles_generic_exception(self, handler, mock_ws):
            mock_ws.receive_text.side_effect = Exception("Unexpected error")

            await handler.handle_connection(mock_ws)

            # Should disconnect on generic error
            # We can't easily assert disconnect was called due to the global manager,
            # but we can verify it doesn't crash

    class TestHandleMessage:
        async def test_ping_message(self, handler, mock_ws):
            await handler._handle_message(mock_ws, {"type": "ping"})

            mock_ws.send_json.assert_awaited_once_with({"type": "pong"})

        async def test_subscribe_message(self, handler, mock_ws):
            await handler._handle_message(mock_ws, {
                "type": "subscribe",
                "channels": ["events"],
            })

            mock_ws.send_json.assert_awaited_once_with({
                "type": "subscribed",
                "channels": ["events"],
            })

        async def test_subscribe_no_channels(self, handler, mock_ws):
            await handler._handle_message(mock_ws, {"type": "subscribe"})

            mock_ws.send_json.assert_awaited_once_with({
                "type": "subscribed",
                "channels": [],
            })

        async def test_unknown_message(self, handler, mock_ws):
            await handler._handle_message(mock_ws, {"type": "invalid"})

            mock_ws.send_json.assert_awaited_once_with({
                "type": "error",
                "message": "Unknown message type: invalid",
            })

    class TestBroadcastEvent:
        async def test_broadcast_event(self, handler):
            with patch("app.api.websocket.event_handler.manager") as mock_manager:
                mock_manager.broadcast = AsyncMock()

                await handler.broadcast_event("payment.received", {"amount": 100})

                mock_manager.broadcast.assert_awaited_once_with({
                    "type": "event",
                    "event_type": "payment.received",
                    "data": {"amount": 100},
                })


class TestGlobalManager:
    """Test the global manager instance."""

    def test_global_manager_is_singleton(self):
        from app.api.websocket.event_handler import manager as m1
        from app.api.websocket.event_handler import manager as m2
        assert m1 is m2
        assert isinstance(m1, ConnectionManager)
