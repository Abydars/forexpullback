import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.engine.scanner import scanner_loop
from backend.engine.position_monitor import position_monitor_loop
from backend.mt5_client.reconnect import reconnect_loop
from backend.core.config import config_manager
from backend.mt5_client.symbol_resolver import symbol_resolver

scheduler = AsyncIOScheduler()
_tasks = []

def start_scheduler():
    config_manager.load()
    
    loop = asyncio.get_event_loop()
    _tasks.append(loop.create_task(scanner_loop()))
    _tasks.append(loop.create_task(position_monitor_loop()))
    _tasks.append(loop.create_task(reconnect_loop()))
    
    # scheduler.start()

def stop_scheduler():
    for task in _tasks:
        task.cancel()
    # if scheduler.running:
    #    scheduler.shutdown()
