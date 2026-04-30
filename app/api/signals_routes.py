from fastapi import APIRouter, HTTPException
from sqlalchemy import select, delete
from datetime import datetime, timezone
import pytz
import asyncio
from pydantic import BaseModel
from typing import List

from app.db.session import AsyncSessionLocal
from app.db.models import Signal
from app.mt5_client.client import mt5_client
from app.ws.manager import broadcast
import MetaTrader5 as mt5

router = APIRouter(prefix="/api")

@router.delete("/signals")
async def clear_signals():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Signal))
        await db.commit()
    await broadcast({"type": "log.event", "level": "INFO", "component": "system", "message": "All signals cleared manually", "created_at": datetime.now(pytz.utc).isoformat()})
    return {"status": "ok"}

@router.post("/signals/clear_results")
async def clear_signal_results():
    from sqlalchemy import update
    async with AsyncSessionLocal() as db:
        await db.execute(update(Signal).values(result=None))
        await db.commit()
    return {"status": "ok"}

class CheckResultsRequest(BaseModel):
    use_smart_tp: bool = False

@router.post("/signals/check_results")
async def check_results(req: CheckResultsRequest = CheckResultsRequest()):
    if not mt5_client.is_connected():
        raise HTTPException(status_code=400, detail="MT5 not connected")
        
    from app.core.config import get_config
    cfg = await get_config()
    smart_tp_enabled = req.use_smart_tp and cfg.get("enable_smart_tp", True)
        
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Signal).where(Signal.result == None, Signal.status.in_(["FIRED", "DCA_FIRED"])))
        signals = result.scalars().all()
        
        updated = 0
        live_results = {}
        
        # Group by symbol to avoid fetching rates multiple times
        symbols = list(set([s.symbol for s in signals]))
        rates_cache = {}
        for sym in symbols:
            df = await mt5_client.get_rates(sym, mt5.TIMEFRAME_M5, 1000) # Last ~3 days
            rates_cache[sym] = df
            
        for s in signals:
            df = rates_cache.get(s.symbol)
            if df is None or df.empty:
                continue
                
            # Filter candles that occurred AFTER the signal was created
            # df['time'] is already UTC tz-naive because pd.to_datetime(unit='s') returns naive UTC
            # s.created_at is also naive UTC
            future_df = df[df['time'] >= s.created_at]
            
            if future_df.empty:
                continue
                
            tp = s.tp
            sl = s.sl
            entry = s.entry
            
            if not tp or not sl or not entry:
                continue
                
            res = None
            
            is_buy = str(s.direction).lower() in ["buy", "bullish"]
            is_sell = str(s.direction).lower() in ["sell", "bearish"]
            
            for idx, row in future_df.iterrows():
                high = row['high']
                low = row['low']
                
                if is_buy:
                    if low <= sl:
                        res = "SL HIT"
                        break
                    elif high >= tp:
                        res = "TP HIT"
                        break
                elif is_sell:
                    if high >= sl:
                        res = "SL HIT"
                        break
                    elif low <= tp:
                        res = "TP HIT"
                        break
                else:
                    res = "UNKNOWN DIR"
                    break
                    
                if smart_tp_enabled:
                    # idx is the integer index in the dataframe (if default range index)
                    # wait, iterrows idx is the index label. If index is not sequential integers, this is bad!
                    # Let's find integer index using get_loc
                    int_idx = df.index.get_loc(idx)
                    start_idx = max(0, int_idx - 14)
                    candles = df.iloc[start_idx:int_idx+1]
                    if len(candles) >= 15:
                        signal_age_seconds = (row['time'] - s.created_at).total_seconds()
                        from app.strategy.smart_tp import evaluate_smart_tp_from_candles
                        direction = "buy" if is_buy else "sell"
                        smart_tp_reason = evaluate_smart_tp_from_candles(
                            direction=direction,
                            entry=entry,
                            sl=sl,
                            tp=tp,
                            candles=candles,
                            signal_age_seconds=signal_age_seconds,
                            cfg=cfg
                        )
                        if smart_tp_reason:
                            res = "SMART TP HIT"
                            break
            
            if res:
                s.result = res
                updated += 1
            else:
                # Live progress logic
                current_price = future_df.iloc[-1]['close']
                tp_distance = 0
                sl_distance = 0
                tp_progress = 0
                sl_progress = 0
                
                if is_buy:
                    tp_distance = tp - entry
                    sl_distance = entry - sl
                    if tp_distance > 0: tp_progress = (current_price - entry) / tp_distance
                    if sl_distance > 0: sl_progress = (entry - current_price) / sl_distance
                elif is_sell:
                    tp_distance = entry - tp
                    sl_distance = sl - entry
                    if tp_distance > 0: tp_progress = (entry - current_price) / tp_distance
                    if sl_distance > 0: sl_progress = (current_price - entry) / sl_distance
                
                status = "IN PROGRESS"
                if tp_progress >= 0.75:
                    status = "NEAR TP"
                elif sl_progress >= 0.75:
                    status = "NEAR SL"
                elif tp_progress > sl_progress and tp_progress > 0:
                    status = "MOVING TO TP"
                elif sl_progress > tp_progress and sl_progress > 0:
                    status = "MOVING TO SL"
                
                live_results[s.id] = {
                    "live_result_status": status,
                    "tp_progress": tp_progress,
                    "sl_progress": sl_progress,
                    "current_price": current_price
                }
                
        if updated > 0:
            await db.commit()
            
    return {"status": "ok", "updated": updated, "live_results": live_results}

class BulkDeleteRequest(BaseModel):
    ids: List[int]

@router.post("/signals/delete_bulk")
async def delete_bulk_signals(req: BulkDeleteRequest):
    if not req.ids:
        return {"status": "ok", "deleted": 0}
        
    from app.db.session import AsyncSessionLocal
    from app.db.models import Signal, Event
    from sqlalchemy import delete
    
    async with AsyncSessionLocal() as db:
        stmt = delete(Signal).where(Signal.id.in_(req.ids))
        res = await db.execute(stmt)
        deleted_count = res.rowcount
        
        if deleted_count > 0:
            db.add(Event(
                level="info",
                component="System",
                message=f"Deleted {deleted_count} selected signals."
            ))
            await db.commit()
            
    return {"status": "ok", "deleted": deleted_count}
