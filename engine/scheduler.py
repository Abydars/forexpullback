from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.config import config_manager
from engine.scanner import scanner_loop
from engine.position_monitor import monitor_loop
import asyncio

scheduler = AsyncIOScheduler()
_loop_tasks = []

def start_scheduler():
    config_manager.load()
    scheduler.start()
    
    loop = asyncio.get_event_loop()
    _loop_tasks.append(loop.create_task(scanner_loop()))
    _loop_tasks.append(loop.create_task(monitor_loop()))

def stop_scheduler():
    scheduler.shutdown()
    for task in _loop_tasks:
        task.cancel()
