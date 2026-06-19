import json
from typing import Dict, List, Any
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Maps user_id -> list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: int):
        """Send raw text message to a specific user's active connections."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass

    async def send_personal_json(self, data: Any, user_id: int):
        """Send JSON message to a specific user's active connections."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(data)
                except Exception:
                    pass

    async def broadcast(self, message: str):
        """Broadcast text message to all active connections."""
        for user_conns in self.active_connections.values():
            for connection in user_conns:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass
                    
    async def broadcast_json(self, data: Any):
        """Broadcast JSON message to all active connections."""
        for user_conns in self.active_connections.values():
            for connection in user_conns:
                try:
                    await connection.send_json(data)
                except Exception:
                    pass

manager = ConnectionManager()
