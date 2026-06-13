"""WebSocket event handler for real-time updates."""
import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        dead_connections = set()
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        self._connections -= dead_connections

    async def send_to_agent(self, agent_id: str, message: dict) -> None:
        """Send a message to a specific agent's connections."""
        # In a production system, you'd maintain a mapping of agent_id -> connections
        await self.broadcast(message)


manager = ConnectionManager()


class WebSocketEventHandler:
    """Handles WebSocket connections for real-time event streaming."""

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection."""
        await manager.connect(websocket)
        logger = logging.getLogger(__name__)
        logger.info("WebSocket client connected")

        try:
            while True:
                # Keep connection alive and handle incoming messages
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    await self._handle_message(websocket, message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })
        except WebSocketDisconnect:
            await manager.disconnect(websocket)
            logger.info("WebSocket client disconnected")
        except Exception as e:
            await manager.disconnect(websocket)
            logger.error("WebSocket error: %s", str(e))

    async def _handle_message(self, websocket: WebSocket, message: dict) -> None:
        """Handle an incoming WebSocket message."""
        msg_type = message.get("type", "")

        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})
        elif msg_type == "subscribe":
            # Handle subscription to specific event types
            await websocket.send_json({
                "type": "subscribed",
                "channels": message.get("channels", []),
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
            })

    async def broadcast_event(self, event_type: str, data: dict) -> None:
        """Broadcast a domain event to all connected clients."""
        await manager.broadcast({
            "type": "event",
            "event_type": event_type,
            "data": data,
        })
