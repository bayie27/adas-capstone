from fastapi import WebSocket
import logging

logger = logging.getLogger("uvicorn.error")

class ConnectionManager:
    def __init__(self) -> None:
        # Stores all active WebSocket connections from the React frontend
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast_alert(self, alert_data: dict) -> None:
        for connection in self.active_connections:
            try:
                await connection.send_json(alert_data)
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")

# Create a global instance to be used across the app
manager = ConnectionManager()