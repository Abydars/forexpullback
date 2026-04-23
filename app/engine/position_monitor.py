import asyncio
import MetaTrader5 as mt5
from app.mt5_client.client import mt5_client
from app.db.session import AsyncSessionLocal
from app.db.models import Trade
from sqlalchemy import select
from app.ws.manager import broadcast
from datetime import datetime
import pytz
from app.core.config import get_config

async def evaluate_smart_exit(p: dict, t, symbol: str) -> str | None:
    if p['profit'] <= 0:
        return None
        
    df = await mt5_client.get_rates(symbol, mt5.TIMEFRAME_M5, 5)
    if df.empty or len(df) < 3: return None
    
    last = df.iloc[-2]
    prev = df.iloc[-3]
    
    entry = t.entry_price
    tp = t.tp
    
    if p['type'] == mt5.ORDER_TYPE_BUY:
        if tp and tp > entry:
            tp_dist = tp - entry
            max_reached = max(last['high'], prev['high'], p['price_current']) - entry
            
            if max_reached >= tp_dist * 0.8:
                # 1. LIVE Exit: If price drops back to 60% after reaching 80%, exit instantly!
                if p['price_current'] - entry <= tp_dist * 0.6:
                    return "Smart TP: Live Rejection (Retraced from 80% to 60% of TP)"
                    
                # 2. Candle Close Exit: If it holds above 60% but closes red, exit on close.
                if last['close'] < last['open']:
                    return "Smart TP: Momentum lost near TP (80%+ reached)"
                    
        # Bearish Reversal (Closed below previous candle's lowest point)
        if last['close'] < last['open'] and last['close'] < prev['low']:
            return "Smart TP: Bearish Reversal Detected"
    else:
        if tp and tp < entry:
            tp_dist = entry - tp
            max_reached = entry - min(last['low'], prev['low'], p['price_current'])
            
            if max_reached >= tp_dist * 0.8:
                if entry - p['price_current'] <= tp_dist * 0.6:
                    return "Smart TP: Live Rejection (Retraced from 80% to 60% of TP)"
                    
                if last['close'] > last['open']:
                    return "Smart TP: Momentum lost near TP (80%+ reached)"
                    
        # Bullish Reversal (Closed above previous candle's highest point)
        if last['close'] > last['open'] and last['close'] > prev['high']:
            return "Smart TP: Bullish Reversal Detected"
                
    return None

async def monitor_loop():
    while True:
        from app.core.state import state
        if not mt5_client.is_connected():
            await asyncio.sleep(0.5)
            continue
            
        try:
            positions = await mt5_client.get_positions()
            acc = await mt5_client.account_info()
            if acc:
                await broadcast({
                    "type": "account.tick",
                    "balance": acc['balance'],
                    "equity": acc['equity'],
                    "margin": acc['margin'],
                    "currency": acc['currency']
                })
            
            pos_dict = {p['ticket']: p for p in positions}
            
            await broadcast({
                "type": "positions.update",
                "positions": positions
            })
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Trade).where(Trade.closed_at == None))
                open_trades = result.scalars().all()
                
                for t in open_trades:
                    if t.ticket not in pos_dict:
                        def _get_hist():
                            return mt5.history_deals_get(position=t.ticket)
                        history = await asyncio.to_thread(_get_hist)
                        
                        t.closed_at = datetime.now(pytz.utc)
                        
                        if history and len(history) > 0:
                            exit_deal = history[-1]
                            t.exit_price = exit_deal.price
                            t.pnl = exit_deal.profit
                            t.commission = exit_deal.commission
                            t.swap = exit_deal.swap
                        else:
                            # Fallback if history is not immediately available
                            t.exit_price = t.entry_price
                            t.pnl = 0.0
                            t.commission = 0.0
                            t.swap = 0.0
                            
                        await db.commit()
                        
                        await broadcast({
                            "type": "trade.closed",
                            "trade": {
                                "ticket": t.ticket, "symbol": t.symbol, "direction": t.direction,
                                "lot": t.lot, "entry_price": t.entry_price, "exit_price": t.exit_price,
                                "pnl": t.pnl, "sl": t.sl, "tp": t.tp
                            }
                        })
                    else:
                        p = pos_dict[t.ticket]
                        
                        exit_reason = await evaluate_smart_exit(p, t, t.symbol)
                        if exit_reason:
                            res = await mt5_client.position_close(t.ticket)
                            if res and res.get('retcode') == mt5.TRADE_RETCODE_DONE:
                                from app.db.models import Event
                                e = Event(level="INFO", component="smart_tp", message=f"Closed {t.ticket} ({t.symbol}): {exit_reason} at +${p['profit']:.2f}")
                                db.add(e)
                                await db.commit()
                                await broadcast({"type": "log.event", "level": "INFO", "component": "smart_tp", "message": e.message, "created_at": datetime.now(pytz.utc).isoformat()})
                                continue
                                
                        # Trailing Stop (Starts at 50% of TP)
                        cfg = await get_config()
                        if cfg.get("trailing", True) and t.tp:
                            tp_dist = abs(t.tp - t.entry_price)
                            current_dist = p['price_current'] - t.entry_price if p['type'] == mt5.ORDER_TYPE_BUY else t.entry_price - p['price_current']
                            
                            if tp_dist > 0 and current_dist >= (tp_dist * 0.5):
                                info = mt5.symbol_info(t.symbol)
                                if info:
                                    trail_pips = float(cfg.get("trailing_distance_pips", 10.0))
                                    
                                    digits = info.digits
                                    if "JPY" in t.symbol:
                                        pip_size = 0.01
                                    elif digits in [3, 5]:
                                        pip_size = info.point * 10
                                    else:
                                        pip_size = info.point
                                        
                                    dist_points = trail_pips * pip_size
                                    
                                    new_sl = None
                                    if p['type'] == mt5.ORDER_TYPE_BUY:
                                        pot_sl = p['price_current'] - dist_points
                                        if pot_sl > t.entry_price and (not t.sl or pot_sl > t.sl):
                                            new_sl = float(f"{pot_sl:.5f}")
                                    else:
                                        pot_sl = p['price_current'] + dist_points
                                        if pot_sl < t.entry_price and (not t.sl or pot_sl < t.sl):
                                            new_sl = float(f"{pot_sl:.5f}")
                                            
                                    if new_sl:
                                        req = {
                                            "action": mt5.TRADE_ACTION_SLTP,
                                            "position": t.ticket,
                                            "symbol": t.symbol,
                                            "sl": new_sl,
                                            "tp": t.tp
                                        }
                                        res_sl = await mt5_client.order_send(req)
                                        if res_sl and res_sl.get('retcode') == mt5.TRADE_RETCODE_DONE:
                                            t.sl = new_sl
                                            await db.commit()
            print("Monitor error:", e)
            
        await asyncio.sleep(0.2)
