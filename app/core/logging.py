import logging
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models import EventRecord

# Provide basic logging that also inserts into SQLite events table
class SQLiteHandler(logging.Handler):
    def emit(self, record):
        try:
            db = SessionLocal()
            event = EventRecord(
                level=record.levelname,
                component=record.name,
                message=self.format(record),
                data=None # Store structured data if needed
            )
            db.add(event)
            db.commit()
            db.close()
        except Exception:
            self.handleError(record)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # SQLite handler
    sqh = SQLiteHandler()
    sqh.setLevel(logging.INFO)
    sqh.setFormatter(formatter)
    logger.addHandler(sqh)

setup_logging()
