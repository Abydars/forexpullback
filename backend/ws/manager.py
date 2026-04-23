import json
import logging
import asyncio
from typing import List, Any
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def handle_connection(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                    if payload.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logging.debug(f"WebSocket disconnected: {e}")
        finally:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: Any):
        if not self.active_connections:
            return
            
        message = {"type": event_type, "data": data}
        
        # We need to gather to handle exceptions per connection
        async def send(ws: WebSocket):
            try:
                await ws.send_json(message)
            except Exception:
                pass
                
        await asyncio.gather(*(send(ws) for ws in self.active_connections))

ws_manager = WebSocketManager()
