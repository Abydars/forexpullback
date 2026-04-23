from fastapi import APIRouter, Depends, HTTPException
from db.session import get_db
from db.models import Trade
from mt5_client.client import mt5_client
from core.logging import log_event

router = APIRouter()

@router.get("")
def get_trades(status: str = None, db=Depends(get_db)):
    query = db.query(Trade)
    if status == "open":
        query = query.filter(Trade.closed_at == None)
    elif status == "closed":
        query = query.filter(Trade.closed_at != None)
        
    trades = query.order_by(Trade.opened_at.desc()).all()
    
    return [
        {
            "id": t.id,
            "ticket": t.ticket,
            "symbol": t.symbol,
            "direction": t.direction,
            "lot": t.lot,
            "entry_price": t.entry_price,
            "sl": t.sl,
            "tp": t.tp,
            "opened_at": t.opened_at,
            "closed_at": t.closed_at,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "commission": t.commission,
            "swap": t.swap,
            "comment": t.comment
        } for t in trades
    ]

@router.post("/{ticket}/close")
def close_trade(ticket: int, db=Depends(get_db)):
    if not mt5_client.is_connected():
        raise HTTPException(status_code=400, detail="MT5 not connected")
        
    result = mt5_client.position_close(ticket)
    
    if result and getattr(result, "retcode", 0) == 10009:
        log_event("info", "trades", f"Manual close initiated for {ticket}")
        return {"status": "success"}
    else:
        raise HTTPException(status_code=400, detail="Close failed")
