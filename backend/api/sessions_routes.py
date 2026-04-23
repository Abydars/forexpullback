from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.db.session import get_db
from backend.db.models import TradingSession
from backend.core.logging import log_event

router = APIRouter()

class SessionCreate(BaseModel):
    name: str
    start_time: str
    end_time: str
    tz: str
    days_mask: int
    enabled: bool

@router.get("")
def get_sessions(db=Depends(get_db)):
    sessions = db.query(TradingSession).all()
    return [{"id": s.id, "name": s.name, "start_time": s.start_time, "end_time": s.end_time, "tz": s.tz, "days_mask": s.days_mask, "enabled": s.enabled} for s in sessions]

@router.post("")
def create_session(req: SessionCreate, db=Depends(get_db)):
    sess = TradingSession(**req.dict())
    db.add(sess)
    db.commit()
    db.refresh(sess)
    log_event("info", "sessions", f"Created session {sess.name}")
    return {"id": sess.id, "name": sess.name, "start_time": sess.start_time, "end_time": sess.end_time, "tz": sess.tz, "days_mask": sess.days_mask, "enabled": sess.enabled}

@router.put("/{session_id}")
def update_session(session_id: int, req: SessionCreate, db=Depends(get_db)):
    sess = db.query(TradingSession).filter(TradingSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Not found")
    
    for k, v in req.dict().items():
        setattr(sess, k, v)
        
    db.commit()
    log_event("info", "sessions", f"Updated session {sess.name}")
    return {"id": sess.id, "name": sess.name, "start_time": sess.start_time, "end_time": sess.end_time, "tz": sess.tz, "days_mask": sess.days_mask, "enabled": sess.enabled}

@router.delete("/{session_id}")
def delete_session(session_id: int, db=Depends(get_db)):
    sess = db.query(TradingSession).filter(TradingSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(sess)
    db.commit()
    log_event("info", "sessions", f"Deleted session {sess.name}")
    return {"status": "success"}
