from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
from app.core.auth import verify_access_token

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(event)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

async def broadcast(event: dict):
    await manager.broadcast(event)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.cookies.get("auth_token")
    if not verify_access_token(token):
        await websocket.close(code=1008)
        return
        
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            pass
    except Exception:
        pass
    except BaseException:
        pass
    finally:
        manager.disconnect(websocket)
