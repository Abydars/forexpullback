from fastapi import APIRouter, Depends
from backend.db.session import get_db
from backend.db.models import Signal

router = APIRouter()

@router.get("")
def get_signals(limit: int = 20, status: str = None, db=Depends(get_db)):
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    signals = query.order_by(Signal.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "direction": s.direction,
            "score": s.score,
            "htf_bias": s.htf_bias,
            "entry": s.entry,
            "sl": s.sl,
            "tp": s.tp,
            "reason": s.reason,
            "created_at": s.created_at,
            "status": s.status
        }
        for s in signals
    ]
