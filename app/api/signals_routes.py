from fastapi import APIRouter, HTTPException
from sqlalchemy import select, delete
from datetime import datetime, timezone
import pytz
import asyncio

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

@router.post("/signals/check_results")
async def check_results():
    if not mt5_client.is_connected():
        raise HTTPException(status_code=400, detail="MT5 not connected")
        
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Signal).where(Signal.result == None, Signal.status.in_(["FIRED", "DCA_FIRED"])))
        signals = result.scalars().all()
        
        updated = 0
        
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
            
            for _, row in future_df.iterrows():
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
            
            if res:
                s.result = res
                updated += 1
                
        if updated > 0:
            await db.commit()
            
    return {"status": "ok", "updated": updated}
