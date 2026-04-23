import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket, WebSocketDisconnect

from backend.db.session import init_db
from backend.core.config import config_manager
from backend.api import mt5_routes, config_routes, sessions_routes, signals_routes, trades_routes, engine_routes
from backend.ws.manager import ws_manager
from backend.engine.scheduler import start_scheduler, stop_scheduler
from backend.core.state import engine_state

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()

app = FastAPI(title="Forex Pullback System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"], # Allow all for local dev simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mt5_routes.router, prefix="/api/mt5", tags=["mt5"])
app.include_router(config_routes.router, prefix="/api/config", tags=["config"])
app.include_router(sessions_routes.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(signals_routes.router, prefix="/api/signals", tags=["signals"])
app.include_router(trades_routes.router, prefix="/api/trades", tags=["trades"])
app.include_router(engine_routes.router, prefix="/api/engine", tags=["engine"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.handle_connection(websocket)

@app.get("/api/status")
def get_status():
    return {
        "engine_state": engine_state.model_dump() if hasattr(engine_state, 'model_dump') else engine_state.dict(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
