from fastapi import APIRouter
from app.core.state import state
from app.mt5_client.client import mt5_client
from app.ws.manager import broadcast

router = APIRouter(prefix="/api")

@router.get("/status")
async def get_status():
    return {
        "engine_running": state.engine_running,
        "mt5_connected": mt5_client.is_connected(),
        "today_pnl": state.today_pnl,
        "active_sessions_count": getattr(state, "active_sessions_count", 0)
    }

from app.core.config import get_config, update_config

@router.post("/engine/start")
async def start_e():
    state.engine_running = True
    cfg = await get_config()
    cfg["engine_running"] = True
    await update_config(cfg)
    await broadcast({"type": "engine.status", "state": "active"})
    return {"status": "started"}

@router.post("/engine/stop")
async def stop_e():
    state.engine_running = False
    cfg = await get_config()
    cfg["engine_running"] = False
    await update_config(cfg)
    await broadcast({"type": "engine.status", "state": "stopped"})
    return {"status": "stopped"}

@router.get("/initial_data")
async def get_initial_data():
    from app.db.session import AsyncSessionLocal
    from app.db.models import Trade, Signal, Event
    from sqlalchemy import select
    from app.engine.scanner import latest_scan_results
    
    async with AsyncSessionLocal() as db:
        trades_res = await db.execute(select(Trade).order_by(Trade.opened_at.desc()).limit(100))
        trades = trades_res.scalars().all()
        
        signals_res = await db.execute(select(Signal).order_by(Signal.created_at.desc()))
        signals = signals_res.scalars().all()
        
        events_res = await db.execute(select(Event).order_by(Event.created_at.desc()).limit(50))
        events = events_res.scalars().all()
        
        return {
            "trades": [
                {"ticket": t.ticket, "symbol": t.symbol, "direction": t.direction, "lot": t.lot, 
                 "entry_price": t.entry_price, "exit_price": t.exit_price, "pnl": t.pnl, 
                 "sl": t.sl, "tp": t.tp, "opened_at": t.opened_at.isoformat(), 
                 "closed_at": t.closed_at.isoformat() if t.closed_at else None} for t in trades
            ],
            "signals": [
                {"id": s.id, "symbol": s.symbol, "direction": s.direction, "score": s.score, 
                 "status": s.status, "reason": s.reason, "created_at": s.created_at.isoformat(),
                 "result": s.result} for s in signals
            ],
            "events": [
                {"level": e.level, "component": e.component, "message": e.message, "created_at": e.created_at.isoformat()} for e in events
            ],
            "scanner_status": latest_scan_results
        }
