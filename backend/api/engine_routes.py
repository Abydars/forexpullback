from fastapi import APIRouter
from backend.core.state import engine_state
from backend.core.logging import log_event

router = APIRouter()

@router.post("/start")
def start_engine():
    engine_state.is_running = True
    log_event("info", "engine", "Engine started")
    return {"status": "success", "is_running": engine_state.is_running}

@router.post("/stop")
def stop_engine():
    engine_state.is_running = False
    log_event("info", "engine", "Engine stopped")
    return {"status": "success", "is_running": engine_state.is_running}
