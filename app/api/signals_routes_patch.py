from fastapi import APIRouter
from app.db.session import AsyncSessionLocal
from app.db.models import Signal
from sqlalchemy import select
from datetime import datetime
from app.api.signals_routes import detect_signal_result, next_closed_m1_open_time
from app.mt5_client.client import mt5_client
from app.core.config import cfg
import asyncio
import MetaTrader5 as mt5
import pandas as pd

@router.get("/sl-buffer-analysis")
async def analyze_sl_buffer():
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
