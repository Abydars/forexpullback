from fastapi import APIRouter
from app.core.state import state
from app.binance_client.client import binance_client
from app.ws.manager import broadcast

router = APIRouter(prefix="/api")

@router.get("/status")
async def get_status():
    return {
        "engine_running": state.engine_running,
        "binance_connected": binance_client.is_connected(),
        "today_pnl": state.today_pnl
    }

@router.post("/engine/start")
async def start_e():
    state.engine_running = True
    await broadcast({"type": "engine.status", "state": "active"})
    return {"status": "started"}

@router.post("/engine/stop")
async def stop_e():
    state.engine_running = False
    await broadcast({"type": "engine.status", "state": "stopped"})
    return {"status": "stopped"}

@router.get("/initial_data")
async def get_initial_data():
    from app.db.session import AsyncSessionLocal
    from app.db.models import Trade, Signal, Event
    from sqlalchemy import select
    from app.engine.symbol_universe import symbol_universe
    from datetime import datetime, timezone
    
    async with AsyncSessionLocal() as db:
        trades_res = await db.execute(select(Trade).order_by(Trade.opened_at.desc()).limit(100))
        trades = trades_res.scalars().all()
        
        signals_res = await db.execute(select(Signal).order_by(Signal.created_at.desc()).limit(50))
        signals = signals_res.scalars().all()
        
        events_res = await db.execute(select(Event).order_by(Event.created_at.desc()).limit(50))
        events = events_res.scalars().all()
        
        return {
            "trades": [
                {"ticket": t.id, "symbol": t.symbol, "direction": t.direction, "quantity": t.quantity, 
                 "entry_price": t.entry_price, "exit_price": t.exit_price, "pnl": t.pnl, 
                 "sl": t.sl, "tp": t.tp, "opened_at": t.opened_at.isoformat(), 
                 "closed_at": t.closed_at.isoformat() if t.closed_at else None} for t in trades
            ],
            "signals": [
                {"id": s.id, "symbol": s.symbol, "direction": s.direction, "score": s.score, 
                 "status": s.status, "reason": s.reason, "created_at": s.created_at.isoformat()} for s in signals
            ],
            "events": [
                {"level": e.level, "component": e.component, "message": e.message, "created_at": e.created_at.isoformat()} for e in events
            ],
            "current_universe": {
                "symbols": getattr(symbol_universe, 'cached_universe', []),
                "source_mode": getattr(symbol_universe, 'last_mode', 'manual'),
                "metadata": getattr(symbol_universe, 'last_metadata', {}),
                "updated_at": datetime.now(timezone.utc).isoformat() if getattr(symbol_universe, 'cached_universe', []) else None
            }
        }
