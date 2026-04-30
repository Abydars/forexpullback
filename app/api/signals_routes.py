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
import pandas as pd

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

def next_closed_m1_open_time(dt):
    ts = pd.Timestamp(dt)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)

    replay = ts.floor("min")
    if ts.second > 0 or ts.microsecond > 0 or ts.nanosecond > 0:
        replay = replay + pd.Timedelta(minutes=1)

    return replay

def detect_signal_result(direction, high, low, open_price, entry, sl, tp, spread_price, tp_buffer_mult, sl_buffer_mult, same_candle_policy):
    is_buy = str(direction).lower() in ["buy", "bullish"]
    is_sell = str(direction).lower() in ["sell", "bearish"]
    
    tp_effective = tp
    sl_effective = sl
    res = None
    both_touched = False
    
    if is_buy:
        tp_effective = tp + (spread_price * tp_buffer_mult)
        sl_effective = sl - (spread_price * sl_buffer_mult)
        sl_touched = low <= sl_effective
        tp_touched = high >= tp_effective
        
        if sl_touched and tp_touched:
            both_touched = True
            if same_candle_policy == "conservative":
                res = "SL HIT"
            elif same_candle_policy == "optimistic":
                res = "TP HIT"
            elif same_candle_policy == "ignore":
                res = None
            elif same_candle_policy == "nearest_open":
                res = "TP HIT" if abs(open_price - tp_effective) < abs(open_price - sl_effective) else "SL HIT"
        elif sl_touched:
            res = "SL HIT"
        elif tp_touched:
            res = "TP HIT"
            
    elif is_sell:
        tp_effective = tp - (spread_price * tp_buffer_mult)
        sl_effective = sl + (spread_price * sl_buffer_mult)
        sl_touched = high >= sl_effective
        tp_touched = low <= tp_effective
        
        if sl_touched and tp_touched:
            both_touched = True
            if same_candle_policy == "conservative":
                res = "SL HIT"
            elif same_candle_policy == "optimistic":
                res = "TP HIT"
            elif same_candle_policy == "ignore":
                res = None
            elif same_candle_policy == "nearest_open":
                res = "TP HIT" if abs(open_price - tp_effective) < abs(open_price - sl_effective) else "SL HIT"
        elif sl_touched:
            res = "SL HIT"
        elif tp_touched:
            res = "TP HIT"
            
    return {
        "result": res,
        "effective_tp": tp_effective,
        "effective_sl": sl_effective,
        "both_touched": both_touched
    }

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
        statuses = ["FIRED", "DCA_FIRED", "SIGNAL_ONLY"]
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
        now_dt = datetime.now()
        
        for sym in symbols:
            info_cache[sym] = await asyncio.to_thread(mt5.symbol_info, sym)
            tick_cache[sym] = await asyncio.to_thread(mt5.symbol_info_tick, sym)
            
            sym_signals = [s for s in signals if s.symbol == sym]
            oldest_dt = min([s.created_at.replace(tzinfo=None) for s in sym_signals])
            
            from datetime import timedelta
            
            # Calculate offset between System Naive Time and Broker Naive Time
            tick = tick_cache[sym]
            offset_hours = 0
            if tick and hasattr(tick, 'time'):
                from datetime import datetime as dt_type
                broker_naive = dt_type.utcfromtimestamp(tick.time)
                offset = now_dt - broker_naive
                offset_hours = round(offset.total_seconds() / 3600)
            
            offset_td = timedelta(hours=offset_hours)
            
            date_from = oldest_dt - timedelta(minutes=2)
            date_to = now_dt + timedelta(minutes=2)
            
            broker_date_from = date_from - offset_td
            broker_date_to = date_to - offset_td
            
            df = await mt5_client.get_rates_range(sym, mt5.TIMEFRAME_M1, broker_date_from, broker_date_to)
            if df is not None and not df.empty:
                df['time'] = df['time'] + pd.Timedelta(hours=offset_hours)
                df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
            rates_cache[sym] = df
            
            if smart_tp_enabled:
                df_m5 = await mt5_client.get_rates_range(sym, mt5.TIMEFRAME_M5, broker_date_from, broker_date_to)
                if df_m5 is not None and not df_m5.empty:
                    df_m5['time'] = df_m5['time'] + pd.Timedelta(hours=offset_hours)
                    df_m5 = df_m5.sort_values("time").drop_duplicates("time").reset_index(drop=True)
                rates_cache_m5[sym] = df_m5
            
        for s in signals:
            df = rates_cache.get(s.symbol)
            if df is None or df.empty:
                continue
                
            # Filter candles that occurred AFTER the signal was created
            from datetime import timedelta
            created_at = s.created_at.replace(tzinfo=None)
                
            replay_start = next_closed_m1_open_time(created_at)
            future_df = df[df['time'] >= pd.Timestamp(replay_start)]
            
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
            
            same_candle_policy = cfg.get("signal_result_same_candle_policy", "conservative")
            debug_signal_result_candles = cfg.get("debug_signal_result_candles", False)
            
            from app.strategy.smart_tp import evaluate_smart_tp_from_candles

            for idx, row in future_df.iterrows():
                if row['time'] > now_dt:
                    continue

                high = row['high']
                low = row['low']
                open_price = row.get('open', entry)

                spread_price = get_spread_price(s.symbol, row, info, tick)

                # Smart TP is evaluated BEFORE SL/TP so it can prevent a false SL result
                # when momentum reversal conditions are already met at an M5 boundary.
                if smart_tp_enabled and row['time'].minute % 5 == 0 and row['time'] > created_at:
                    df_m5 = rates_cache_m5.get(s.symbol)
                    if df_m5 is not None and not df_m5.empty:
                        closed_m5 = df_m5[df_m5['time'] < row['time']]
                        if len(closed_m5) >= 15:
                            candles = closed_m5.tail(15)
                            signal_age_seconds = (row['time'] - created_at).total_seconds()
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
                                debug_info = {
                                    "source": "MT5.copy_rates_range",
                                    "timeframe": "M1",
                                    "symbol": s.symbol,
                                    "created_at": created_at.isoformat(),
                                    "replay_start": replay_start.isoformat(),
                                    "hit_candle_time": row['time'].isoformat(),
                                    "candle_open": row.get("open"),
                                    "candle_high": high,
                                    "candle_low": low,
                                    "candle_close": row.get("close"),
                                    "candle_spread": row.get("spread"),
                                    "entry": entry, "sl": sl, "tp": tp,
                                    "effective_tp": tp,
                                    "effective_sl": sl,
                                    "spread_price": spread_price,
                                    "direction": s.direction,
                                    "signal_id": s.id, "result": res, 
                                    "hit_time": row['time'].isoformat(),
                                    "server_now": now_dt.isoformat(),
                                    "smart_tp_reason": smart_tp_reason
                                }
                                break

                detection = detect_signal_result(
                    direction=s.direction,
                    high=high,
                    low=low,
                    open_price=open_price,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    spread_price=spread_price,
                    tp_buffer_mult=tp_buffer_mult,
                    sl_buffer_mult=sl_buffer_mult,
                    same_candle_policy=same_candle_policy
                )

                if detection["result"]:
                    res = detection["result"]
                    debug_info = {
                        "source": "MT5.copy_rates_range",
                        "timeframe": "M1",
                        "symbol": s.symbol,
                        "created_at": created_at.isoformat(),
                        "replay_start": replay_start.isoformat(),
                        "hit_candle_time": row['time'].isoformat(),
                        "candle_open": row.get("open"),
                        "candle_high": high,
                        "candle_low": low,
                        "candle_close": row.get("close"),
                        "candle_spread": row.get("spread"),
                        "entry": entry, "sl": sl, "tp": tp,
                        "effective_tp": detection["effective_tp"],
                        "effective_sl": detection["effective_sl"],
                        "spread_price": spread_price,
                        "direction": s.direction,
                        "signal_id": s.id, "result": res,
                        "hit_time": row['time'].isoformat(),
                        "server_now": now_dt.isoformat(),
                        "both_touched": detection["both_touched"]
                    }
                    break
                    
            if debug_signal_result_candles:
                import logging
                log_lines = []
                log_lines.append(f"[SignalResultDebug] signal_id={s.id} symbol={s.symbol} direction={s.direction} created_at={created_at.isoformat()} replay_start={replay_start.isoformat()}")
                log_lines.append("candles:\\ntime open high low close spread")
                
                target_time = row['time'] if res else replay_start
                mask = df['time'] == target_time
                if mask.any():
                    t_idx = df.index[mask][0]
                    start_idx = max(0, t_idx - 5)
                    end_idx = min(len(df), t_idx + 6)
                    for _, dbg_row in df.iloc[start_idx:end_idx].iterrows():
                        log_lines.append(f"{dbg_row['time']} {dbg_row.get('open')} {dbg_row.get('high')} {dbg_row.get('low')} {dbg_row.get('close')} {dbg_row.get('spread')}")
                else:
                    for _, dbg_row in future_df.head(10).iterrows():
                        log_lines.append(f"{dbg_row['time']} {dbg_row.get('open')} {dbg_row.get('high')} {dbg_row.get('low')} {dbg_row.get('close')} {dbg_row.get('spread')}")
                
                print("\\n".join(log_lines))
            
            if res:
                s.result = res
                updated += 1
                live_results[s.id] = {
                    "live_result_status": res,
                    "debug": debug_info
                }
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
from fastapi import APIRouter
from app.db.session import AsyncSessionLocal
from app.db.models import Signal
from sqlalchemy import select
from datetime import datetime
@router.get("/signals/sl-buffer-analysis")
async def analyze_sl_buffer():
    from app.core.config import get_config
    cfg = await get_config()
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Signal).order_by(Signal.created_at.desc()).limit(1000))
        signals = res.scalars().all()
        
    resolved = [s for s in signals if s.result in ["TP HIT", "SL HIT", "SMART TP HIT"] and s.entry and s.sl and s.tp]
    
    if not resolved:
        return {"data": []}
        
    symbols = list(set([s.symbol for s in resolved]))
    now_dt = datetime.now()
    
    tick_cache = {}
    info_cache = {}
    rates_cache = {}
    
    for sym in symbols:
        info_cache[sym] = await asyncio.to_thread(mt5.symbol_info, sym)
        tick_cache[sym] = await asyncio.to_thread(mt5.symbol_info_tick, sym)
        
        sym_signals = [s for s in resolved if s.symbol == sym]
        oldest_dt = min([s.created_at.replace(tzinfo=None) for s in sym_signals])
        
        from datetime import timedelta
        tick = tick_cache[sym]
        offset_hours = 0
        if tick and hasattr(tick, 'time'):
            from datetime import datetime as dt_type
            broker_naive = dt_type.utcfromtimestamp(tick.time)
            offset = now_dt - broker_naive
            offset_hours = round(offset.total_seconds() / 3600)
            
        offset_td = timedelta(hours=offset_hours)
        date_from = oldest_dt - timedelta(minutes=2)
        date_to = now_dt + timedelta(minutes=2)
        
        broker_date_from = date_from - offset_td
        broker_date_to = date_to - offset_td
        
        df = await mt5_client.get_rates_range(sym, mt5.TIMEFRAME_M1, broker_date_from, broker_date_to)
        if df is not None and not df.empty:
            df['time'] = df['time'] + pd.Timedelta(hours=offset_hours)
            df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
        rates_cache[sym] = df

    analysis = []
    
    tp_buffer_mult = float(cfg.get("signal_result_tp_buffer_spread_mult", 1.5))
    sl_buffer_mult = float(cfg.get("signal_result_sl_buffer_spread_mult", 0.0))
    same_candle_policy = cfg.get("signal_result_same_candle_policy", "conservative")
    
    for s in resolved:
        df = rates_cache.get(s.symbol)
        if df is None or df.empty:
            continue
            
        created_at = s.created_at.replace(tzinfo=None)
        replay_start = next_closed_m1_open_time(created_at)
        future_df = df[df['time'] >= pd.Timestamp(replay_start)]
        
        if future_df.empty:
            continue
            
        R = abs(s.entry - s.sl)
        if R <= 0:
            continue
            
        info = info_cache.get(s.symbol)
        point = info.point if info else 0.00001
        
        scenarios = [0.0, 0.25, 0.50, 0.75, 1.0]
        results = {}
        
        for buf in scenarios:
            if s.direction == "buy":
                adj_sl = s.sl - (buf * R)
            else:
                adj_sl = s.sl + (buf * R)
                
            res_str = None
            for idx, row in future_df.iterrows():
                if row['time'] > now_dt:
                    continue
                    
                spread_price = (row.get("spread") or 0) * point
                det = detect_signal_result(
                    direction=s.direction, high=row['high'], low=row['low'], open_price=row['open'],
                    entry=s.entry, sl=adj_sl, tp=s.tp, spread_price=spread_price,
                    tp_buffer_mult=tp_buffer_mult, sl_buffer_mult=sl_buffer_mult,
                    same_candle_policy=same_candle_policy
                )
                if det["result"]:
                    res_str = det["result"]
                    break
                    
            results[str(buf)] = res_str
            
        analysis.append({
            "id": s.id, "symbol": s.symbol, "direction": s.direction, "scenarios": results,
            "original_result": s.result
        })
        
    return {"data": analysis}
