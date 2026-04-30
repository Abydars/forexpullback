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
    include_skipped: bool = False

@router.post("/signals/check_results")
async def check_results(req: CheckResultsRequest = CheckResultsRequest()):
    if not mt5_client.is_connected():
        raise HTTPException(status_code=400, detail="MT5 not connected")
        
    from app.core.config import get_config
    cfg = await get_config()
    smart_tp_enabled = req.use_smart_tp and cfg.get("enable_smart_tp", True)
        
    async with AsyncSessionLocal() as db:
        statuses = ["FIRED", "DCA_FIRED"]
        if req.include_skipped:
            statuses.extend(["SKIPPED", "DCA_SKIPPED"])
            
        result = await db.execute(select(Signal).where(Signal.result == None, Signal.status.in_(statuses)))
        signals = result.scalars().all()
        
        updated = 0
        live_results = {}
        
        # Group by symbol to avoid fetching rates multiple times
        symbols = list(set([s.symbol for s in signals]))
        rates_cache = {}
        rates_cache_m5 = {}
        info_cache = {}
        tick_cache = {}
        
        tp_buffer_mult = float(cfg.get("signal_result_tp_buffer_spread_mult", 1.5))
        sl_buffer_mult = float(cfg.get("signal_result_sl_buffer_spread_mult", 0.0))
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        
        for sym in symbols:
            info_cache[sym] = await mt5_client.get_symbol_info(sym)
            tick_cache[sym] = await mt5_client.get_symbol_tick(sym)
            
            sym_signals = [s for s in signals if s.symbol == sym]
            oldest_dt = min([s.created_at for s in sym_signals])
            
            # Calculate approx minutes since the oldest signal. 
            # We add a 120 min buffer for Smart TP lookback history
            mins_diff = int((now_dt - oldest_dt).total_seconds() / 60)
            count = max(3000, mins_diff + 120)
            
            df = await mt5_client.get_rates(sym, mt5.TIMEFRAME_M1, count)
            rates_cache[sym] = df
            
            if smart_tp_enabled:
                count_m5 = max(1000, int(mins_diff / 5) + 24)
                df_m5 = await mt5_client.get_rates(sym, mt5.TIMEFRAME_M5, count_m5)
                rates_cache_m5[sym] = df_m5
            
        for s in signals:
            df = rates_cache.get(s.symbol)
            if df is None or df.empty:
                continue
                
            # Filter candles that occurred AFTER the signal was created
            # df['time'] is already UTC tz-naive because pd.to_datetime(unit='s') returns naive UTC
            # s.created_at is also naive UTC
            from datetime import timedelta
            replay_start = s.created_at + timedelta(minutes=1)
            future_df = df[df['time'] >= replay_start]
            
            if future_df.empty:
                continue
                
            tp = s.tp
            sl = s.sl
            entry = s.entry
            
            if not tp or not sl or not entry:
                continue
                
            info = info_cache.get(s.symbol)
            tick = tick_cache.get(s.symbol)
            
            def get_spread_price(sym, row, info_obj, tick_obj):
                spread_val = row.get('spread')
                if spread_val is not None and not pd.isna(spread_val):
                    point = info_obj.point if info_obj else 0.00001
                    return spread_val * point
                if tick_obj and hasattr(tick_obj, 'ask') and hasattr(tick_obj, 'bid'):
                    return tick_obj.ask - tick_obj.bid
                return 0.0
                
            res = None
            ignored_tp_touch_count = 0
            
            is_buy = str(s.direction).lower() in ["buy", "bullish"]
            is_sell = str(s.direction).lower() in ["sell", "bearish"]
            
            for idx, row in future_df.iterrows():
                high = row['high']
                low = row['low']
                
                spread_price = get_spread_price(s.symbol, row, info, tick)
                
                if is_buy:
                    tp_effective = tp + (spread_price * tp_buffer_mult)
                    if low <= sl:
                        res = "SL HIT"
                        break
                    elif high >= tp_effective:
                        res = "TP HIT"
                        break
                    elif high >= tp:
                        ignored_tp_touch_count += 1
                elif is_sell:
                    tp_effective = tp - (spread_price * tp_buffer_mult)
                    if high >= sl:
                        res = "SL HIT"
                        break
                    elif low <= tp_effective:
                        res = "TP HIT"
                        break
                    elif low <= tp:
                        ignored_tp_touch_count += 1
                else:
                    res = "UNKNOWN DIR"
                    break
                    
                if smart_tp_enabled:
                    # An M5 candle is fully closed exactly when the new M1 candle's minute is a multiple of 5
                    if row['time'].minute % 5 == 0 and row['time'] > s.created_at:
                        df_m5 = rates_cache_m5.get(s.symbol)
                        if df_m5 is not None and not df_m5.empty:
                            closed_m5 = df_m5[df_m5['time'] < row['time']]
                            if len(closed_m5) >= 15:
                                candles = closed_m5.tail(15)
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
                    "current_price": current_price,
                    "ignored_tp_touch_count": ignored_tp_touch_count
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
