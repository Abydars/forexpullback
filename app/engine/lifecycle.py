import asyncio
from app.engine.scanner import scan_loop
from app.engine.position_monitor import monitor_loop

_tasks = []

async def start_engine():
    global _tasks
    from app.core.state import state
    state.engine_running = False
    _tasks = [
        asyncio.create_task(scan_loop()),
        asyncio.create_task(monitor_loop())
    ]

async def stop_engine():
    global _tasks
    for t in _tasks:
        t.cancel()
