import json
from app.core.config import get_config, update_config
from app.db.models import AsyncSessionLocal, SessionModel, Trade, Signal, Event
from sqlalchemy import select
from app.core.state import state
from app.binance_client.client import binance_client
from app.engine.lifecycle import start_engine, stop_engine
from app.engine.position_monitor import close_trade_binance

async def handle_rpc(websocket, msg: dict):
    req_id = msg.get("id")
    method = msg.get("method", "GET")
    path = msg.get("path", "")
    body = msg.get("body", {})

    try:
        data = await route_rpc(method, path, body)
        await websocket.send_json({"type": "rpc_response", "id": req_id, "status": 200, "data": data})
    except Exception as e:
        await websocket.send_json({"type": "rpc_response", "id": req_id, "status": 500, "data": str(e)})

async def route_rpc(method: str, path: str, body: dict):
    if path == "/api/status" and method == "GET":
        return {"engine_running": state.engine_running}
        
    elif path == "/api/initial_data" and method == "GET":
        cfg = await get_config()
        if "dashboard_password" in cfg: cfg["dashboard_password"] = ""
        
        async with AsyncSessionLocal() as db:
            sessions = (await db.execute(select(SessionModel))).scalars().all()
            trades = (await db.execute(select(Trade).order_by(Trade.created_at.desc()).limit(100))).scalars().all()
            signals = (await db.execute(select(Signal).order_by(Signal.created_at.desc()).limit(100))).scalars().all()
            events = (await db.execute(select(Event).order_by(Event.created_at.desc()).limit(100))).scalars().all()
            
        from app.engine.symbol_universe import symbol_universe
        universe = symbol_universe.last_metadata if hasattr(symbol_universe, 'last_metadata') else {}
        
        return {
            "config": cfg,
            "sessions": [s.__dict__ for s in sessions if not s.__dict__.pop('_sa_instance_state', None)],
            "trades": [{"id": t.id, "symbol": t.symbol, "direction": t.direction, "quantity": t.quantity,
                        "entry_price": t.entry_price, "exit_price": t.exit_price, "pnl": t.pnl, "commission": t.commission,
                        "sl": t.sl, "tp": t.tp, "status": t.status, "note": t.note,
                        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                        "closed_at": t.closed_at.isoformat() if t.closed_at else None} for t in trades],
            "signals": [{"id": s.id, "symbol": s.symbol, "direction": s.direction, "score": s.score,
                         "status": s.status, "reason": s.reason, "created_at": s.created_at.isoformat() if s.created_at else None} for s in signals],
            "events": [{"id": e.id, "level": e.level, "component": e.component, "message": e.message,
                        "created_at": e.created_at.isoformat() if e.created_at else None} for e in events],
            "binance_connected": binance_client.is_connected(),
            "engine_running": state.engine_running,
            "current_universe": {"symbols": list(universe.values())}
        }
        
    elif path == "/api/config" and method == "GET":
        cfg = await get_config()
        if "dashboard_password" in cfg: cfg["dashboard_password"] = ""
        return cfg
        
    elif path == "/api/config" and method == "PATCH":
        from app.core.auth import hash_password
        if "dashboard_password" in body:
            pw = body["dashboard_password"]
            if pw and pw.strip():
                body["dashboard_password"] = hash_password(pw.strip())
            else:
                del body["dashboard_password"]
        await update_config(body)
        from app.engine.symbol_universe import symbol_universe
        import time
        new_cfg = await get_config()
        symbol_universe.cached_universe = await symbol_universe.build_scan_symbols(new_cfg)
        symbol_universe.last_refresh = time.time()
        return {"status": "ok"}
        
    elif path == "/api/sessions" and method == "GET":
        async with AsyncSessionLocal() as db:
            sessions = (await db.execute(select(SessionModel))).scalars().all()
            return [s.__dict__ for s in sessions if not s.__dict__.pop('_sa_instance_state', None)]
            
    elif path == "/api/sessions" and method == "PUT":
        async with AsyncSessionLocal() as db:
            await db.execute(SessionModel.__table__.delete())
            for s in body.get("sessions", []):
                db.add(SessionModel(id=s["id"], name=s["name"], start_time=s["start_time"],
                                    end_time=s["end_time"], tz=s["tz"], days_mask=s["days_mask"], enabled=s["enabled"]))
            await db.commit()
        return {"status": "ok"}
        
    elif path == "/api/binance/connect" and method == "POST":
        cfg = {"binance_api_key": body.get("api_key"), "binance_api_secret": body.get("api_secret"), "binance_testnet": body.get("testnet")}
        await update_config(cfg)
        await binance_client.initialize()
        return {"status": "ok" if binance_client.is_connected() else "failed"}
        
    elif path == "/api/binance/disconnect" and method == "POST":
        await update_config({"binance_api_key": "", "binance_api_secret": ""})
        binance_client.api_key = None
        binance_client.api_secret = None
        return {"status": "ok"}
        
    elif path == "/api/binance/status" and method == "GET":
        return {"connected": binance_client.is_connected()}
        
    elif path == "/api/engine/start" and method == "POST":
        await start_engine()
        return {"status": "started"}
        
    elif path == "/api/engine/stop" and method == "POST":
        await stop_engine()
        return {"status": "stopped"}
        
    elif path.startswith("/api/trades/") and path.endswith("/close") and method == "POST":
        trade_id = int(path.split("/")[3])
        async with AsyncSessionLocal() as db:
            trade = await db.get(Trade, trade_id)
            if not trade or trade.closed_at: return {"status": "error", "detail": "Invalid or closed trade"}
            success = await close_trade_binance(trade)
            if not success: raise Exception("Failed to close trade on Binance")
        return {"status": "ok"}
        
    elif path == "/api/symbols/preview" and method == "POST":
        from app.engine.symbol_universe import symbol_universe
        await symbol_universe.build_scan_symbols(body)
        return list(symbol_universe.last_metadata.values()) if hasattr(symbol_universe, 'last_metadata') else []
        
    raise Exception(f"RPC Route Not Found: {method} {path}")
