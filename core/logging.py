import logging
from datetime import datetime
import json
import asyncio
from db.session import SessionLocal
from db.models import Event
from ws.manager import ws_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("engine")

def log_event(level: str, component: str, message: str, data: dict = None):
    # Log to python logger
    if level == "error":
        logger.error(f"[{component}] {message} - {data}")
    elif level == "warn":
        logger.warning(f"[{component}] {message} - {data}")
    else:
        logger.info(f"[{component}] {message} - {data}")
        
    # Log to DB
    try:
        with SessionLocal() as db:
            event = Event(
                level=level,
                component=component,
                message=message,
                data=data,
                created_at=datetime.utcnow()
            )
            db.add(event)
            db.commit()
            
            event_dict = {
                "id": event.id,
                "level": event.level,
                "component": event.component,
                "message": event.message,
                "data": event.data,
                "created_at": event.created_at.isoformat()
            }
            
        # Push over WS
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_manager.broadcast("log.event", event_dict))
        except RuntimeError:
            pass # No running loop
    except Exception as e:
        logger.error(f"Failed to log event to DB: {e}")
