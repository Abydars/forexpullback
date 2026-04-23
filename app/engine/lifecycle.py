import asyncio
from app.engine.scanner import scanner_loop
from app.engine.position_monitor import position_monitor_loop
from app.mt5_client.reconnect import auto_reconnect_loop

engine_tasks = []

async def start_engine():
    from app.ui.state import state
    state.engine_running = True
    print("Engine started.")
    
    engine_tasks.append(asyncio.create_task(scanner_loop()))
    engine_tasks.append(asyncio.create_task(position_monitor_loop()))
    engine_tasks.append(asyncio.create_task(auto_reconnect_loop()))

async def stop_engine():
    from app.ui.state import state
    state.engine_running = False
    print("Engine stopped.")
    for task in engine_tasks:
        task.cancel()
    engine_tasks.clear()
