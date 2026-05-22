from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List 
import json 


router = APIRouter(tags=["Real-time Streams"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Pushes structured JSON string messages out to all live browser sessions."""
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.active_connections.remove(connection)

manager = ConnectionManager()

@router.websocket("/ws/market-stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try: 
        while True:
            # keep the connection open
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(websocket)