from pydantic import BaseModel
from typing import Optional

class EngineState(BaseModel):
    is_running: bool = False
    last_loop_time: Optional[str] = None
    mt5_connected: bool = False
    active_sessions_count: int = 0
    open_positions_count: int = 0
    error_message: Optional[str] = None

engine_state = EngineState()
