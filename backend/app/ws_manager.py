from fastapi import WebSocket
import logging

logger = logging.getLogger("uvicorn.error")

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        try:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
        except ValueError:
            logger.warning("Attempted to remove a websocket that was not in the active list.")

    async def broadcast_alert(self, alert_data: dict) -> None:
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(alert_data)
            except Exception as e:
                logger.error(f"Dead websocket detected, marking for removal: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            try:
                self.active_connections.remove(dead)
                logger.info(f"Removed dead connection. Total connections: {len(self.active_connections)}")
            except ValueError:
                pass

# Create a global instance to be used across the app
manager = ConnectionManager()