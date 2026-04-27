from fastapi import APIRouter
from app.mt5_client.client import mt5_client

router = APIRouter(prefix="/api/trades")

@router.post("/{ticket}/close")
async def close_trade(ticket: int):
    res = await mt5_client.position_close(ticket)
    return {"status": "ok", "result": res}

@router.post("/close-all")
async def close_all_trades():
    import asyncio
    import MetaTrader5 as mt5
    from app.engine.config_manager import get_config
    from app.db.session import AsyncSessionLocal
    from app.db.models import Event
    from app.ws.manager import broadcast
    from datetime import datetime
    import pytz
    
    cfg = get_config()
    magic = int(cfg.get("magic_number", 123456))
    
    positions = await mt5_client.get_positions()
    bot_positions = [p for p in positions if p.get('magic') == magic]
    
    if not bot_positions:
        return {"status": "ok", "message": "No bot positions to close", "success": 0, "failed": 0}
        
    close_concurrency = int(cfg.get("close_all_concurrency", 2))
    if close_concurrency < 1: close_concurrency = 1
    sem = asyncio.Semaphore(close_concurrency)
    
    async def close_one_position(p):
        async with sem:
            try:
                return await mt5_client.position_close(p['ticket'])
            except Exception as e:
                return e
                
    tasks = [close_one_position(p) for p in bot_positions]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = 0
    failed_count = 0
    failed_details = []
    
    for i, res in enumerate(results):
        ticket = bot_positions[i]['ticket']
        if isinstance(res, Exception):
            failed_count += 1
            failed_details.append(f"Ticket {ticket}: Exception {str(res)}")
        elif isinstance(res, dict) and res.get('retcode') != mt5.TRADE_RETCODE_DONE:
            failed_count += 1
            failed_details.append(f"Ticket {ticket}: Code {res.get('retcode')} - {res.get('comment')}")
        elif res is None:
            failed_count += 1
            failed_details.append(f"Ticket {ticket}: Unknown failure (None returned)")
        else:
            success_count += 1
            
    log_msg = f"Manual Close-all: Requested {len(bot_positions)}, Success {success_count}, Failed {failed_count}"
    if failed_count > 0:
        log_msg += f" Failures: {', '.join(failed_details)}"
        
    async with AsyncSessionLocal() as db:
        db.add(Event(level="INFO" if failed_count == 0 else "WARN", component="order_manager", message=log_msg))
        await db.commit()
    await broadcast({"type": "log.event", "level": "INFO" if failed_count == 0 else "WARN", "component": "order_manager", "message": log_msg, "created_at": datetime.now(pytz.utc).isoformat()})
    
    return {
        "status": "ok" if failed_count == 0 else "partial",
        "message": log_msg,
        "success": success_count,
        "failed": failed_count,
        "details": failed_details
    }
