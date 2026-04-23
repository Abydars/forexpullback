from datetime import datetime
from db.session import SessionLocal
from db.models import Signal
from ws.manager import ws_manager
from core.logging import log_event
from engine.order_manager import process_signal

async def emit_signal(symbol: str, htf_bias: str, score: float, entry: float, sl: float, tp: float, reason: dict):
    with SessionLocal() as db:
        signal = Signal(
            symbol=symbol,
            direction=htf_bias,
            score=score,
            htf_bias=htf_bias,
            entry=entry,
            sl=sl,
            tp=tp,
            reason=reason,
            created_at=datetime.utcnow(),
            status="NEW"
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        
        signal_dict = {
            "id": signal.id,
            "symbol": signal.symbol,
            "direction": signal.direction,
            "score": signal.score,
            "htf_bias": signal.htf_bias,
            "entry": signal.entry,
            "sl": signal.sl,
            "tp": signal.tp,
            "reason": signal.reason,
            "created_at": signal.created_at.isoformat(),
            "status": signal.status
        }
        
    await ws_manager.broadcast("signal.new", signal_dict)
    log_event("info", "signal_engine", f"New signal for {symbol} ({htf_bias})", signal_dict)
    
    await process_signal(signal.id)
