from fastapi import APIRouter
from app.core.state import state
from app.mt5_client.client import mt5_client
from app.ws.manager import broadcast

router = APIRouter(prefix="/api")

@router.get("/status")
async def get_status():
    return {
        "engine_running": state.engine_running,
        "mt5_connected": mt5_client.is_connected(),
        "today_pnl": state.today_pnl
    }

@router.post("/engine/start")
async def start_e():
    state.engine_running = True
    await broadcast({"type": "engine.status", "state": "active"})
    return {"status": "started"}

@router.post("/engine/stop")
async def stop_e():
    state.engine_running = False
    await broadcast({"type": "engine.status", "state": "stopped"})
    return {"status": "stopped"}
