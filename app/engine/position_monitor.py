import asyncio
import MetaTrader5 as mt5
from app.mt5_client.client import mt5_client
from app.db.session import AsyncSessionLocal
from app.db.models import Trade
from sqlalchemy import select
from app.ws.manager import broadcast
from datetime import datetime
import pytz
import pandas as pd
from app.core.config import get_config

async def evaluate_smart_exit(p: dict, t, symbol: str) -> str | None:
    if p['profit'] <= 0:
        return None
        
    # Minimum trade age (disable smart TP for first 20 mins ~ 4 candles)
    opened_at = t.opened_at
    if opened_at.tzinfo is None: opened_at = opened_at.replace(tzinfo=pytz.utc)
    if (datetime.now(pytz.utc) - opened_at).total_seconds() < 20 * 60:
        return None
        
    df = await mt5_client.get_rates(symbol, mt5.TIMEFRAME_M5, 15)
    if df.empty or len(df) < 15: return None
    
    # Calculate ATR for volatility filter
    df_copy = df.copy()
    df_copy['tr'] = df_copy['high'] - df_copy['low']
    atr = df_copy['tr'].mean()
    
    last = df.iloc[-2]
    prev = df.iloc[-3]
    
    entry = t.entry_price
    tp = t.tp
    
    body_last = abs(last['close'] - last['open'])
    range_last = last['high'] - last['low']
    is_strong = body_last > (range_last * 0.4)
    
    if p['type'] == mt5.ORDER_TYPE_BUY:
        if tp and tp > entry:
            tp_dist = tp - entry
            # Use closed candle prices instead of live tick for 80% -> 60% logic
            max_reached = max(last['high'], prev['high']) - entry
            
            if max_reached >= tp_dist * 0.8:
                if (last['close'] - entry) <= tp_dist * 0.6:
                    return "Smart TP: Closed below 60% after reaching 80%"
                    
        # Momentum Reversal (Bearish)
        if last['close'] < last['open'] and last['close'] < prev['low']:
            move_size = entry - last['close'] if entry > last['close'] else last['close'] - entry
            if move_size > (0.5 * atr):
                if is_strong or (prev['close'] < prev['open']): # Strong or 2-candle confirmation
                    return "Smart TP: Strong Bearish Reversal Detected"
    else:
        if tp and tp < entry:
            tp_dist = entry - tp
            max_reached = entry - min(last['low'], prev['low'])
            
            if max_reached >= tp_dist * 0.8:
                if (entry - last['close']) <= tp_dist * 0.6:
                    return "Smart TP: Closed below 60% after reaching 80%"
                    
        # Momentum Reversal (Bullish)
        if last['close'] > last['open'] and last['close'] > prev['high']:
            move_size = last['close'] - entry if last['close'] > entry else entry - last['close']
            if move_size > (0.5 * atr):
                if is_strong or (prev['close'] > prev['open']):
                    return "Smart TP: Strong Bullish Reversal Detected"
                
    return None

basket_state = {"active": False, "peak_pnl": 0.0}

async def monitor_loop():
    global basket_state
    retry_counts = {}
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
            

            cfg = await get_config()
            magic = int(cfg.get('magic_number', 123456))
            bot_positions = [p for p in positions if p.get('magic') == magic]
            
            enable_basket = cfg.get("enable_basket_trailing", False)
            if enable_basket and len(bot_positions) > 0:
                total_unrealized_pnl = sum(p.get('profit', 0) for p in bot_positions)
                start_usd = float(cfg.get("basket_trailing_start_usd", 5.0))
                drawdown_usd = float(cfg.get("basket_trailing_drawdown_usd", 1.5))
                min_close_usd = float(cfg.get("basket_trailing_min_close_usd", 5.0))
                
                if total_unrealized_pnl >= start_usd:
                    if not basket_state["active"]:
                        basket_state["active"] = True
                        basket_state["peak_pnl"] = total_unrealized_pnl
                        msg = f"Basket trailing activated at +${total_unrealized_pnl:.2f}"
                        async with AsyncSessionLocal() as db:
                            from app.db.models import Event
                            db.add(Event(level="INFO", component="basket", message=msg))
                            await db.commit()
                        await broadcast({"type": "log.event", "level": "INFO", "component": "basket", "message": msg, "created_at": datetime.now(pytz.utc).isoformat()})
                    else:
                        if total_unrealized_pnl > basket_state["peak_pnl"]:
                            basket_state["peak_pnl"] = total_unrealized_pnl
                
                if basket_state["active"]:
                    if total_unrealized_pnl < min_close_usd:
                        msg = f"Basket trailing reset: PnL dropped below minimum close profit (Peak was +${basket_state['peak_pnl']:.2f})"
                        basket_state["active"] = False
                        basket_state["peak_pnl"] = 0.0
                        async with AsyncSessionLocal() as db:
                            from app.db.models import Event
                            db.add(Event(level="INFO", component="basket", message=msg))
                            await db.commit()
                        await broadcast({"type": "log.event", "level": "INFO", "component": "basket", "message": msg, "created_at": datetime.now(pytz.utc).isoformat()})
                    elif basket_state["peak_pnl"] - total_unrealized_pnl >= drawdown_usd:
                        # Close ALL bot positions
                        for p in bot_positions:
                            await mt5_client.position_close(p['ticket'])
                            
                        msg = f"Basket trailing close: secured +${total_unrealized_pnl:.2f} minimum basket profit (Peak: +${basket_state['peak_pnl']:.2f})"
                        async with AsyncSessionLocal() as db:
                            from app.db.models import Event
                            db.add(Event(level="INFO", component="basket", message=msg))
                            await db.commit()
                        await broadcast({"type": "log.event", "level": "INFO", "component": "basket", "message": msg, "created_at": datetime.now(pytz.utc).isoformat()})
                        basket_state["active"] = False
                        basket_state["peak_pnl"] = 0.0
            else:
                basket_state["active"] = False
                basket_state["peak_pnl"] = 0.0
                
            await broadcast({
                "type": "positions.update",
                "positions": positions,
                "basket_state": basket_state
            })
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Trade).where(Trade.closed_at == None))
                open_trades = result.scalars().all()
                
                for t in open_trades:
                    if t.ticket not in pos_dict:
                        def _get_hist():
                            return mt5.history_deals_get(position=t.ticket)
                        history = await asyncio.to_thread(_get_hist)
                        
                        if history and len(history) > 0:
                            exit_deal = history[-1]
                            t.exit_price = exit_deal.price
                            t.pnl = exit_deal.profit
                            t.commission = exit_deal.commission
                            t.swap = exit_deal.swap
                            t.closed_at = datetime.now(pytz.utc)
                            retry_counts.pop(t.ticket, None)
                        else:
                            retries = retry_counts.get(t.ticket, 0)
                            if retries < 15:
                                retry_counts[t.ticket] = retries + 1
                                continue # Retry on next loop (0.2s)
                                
                            # Fallback if history is completely unavailable after 3 seconds
                            t.exit_price = t.entry_price
                            t.pnl = 0.0
                            t.commission = 0.0
                            t.swap = 0.0
                            t.closed_at = datetime.now(pytz.utc)
                            retry_counts.pop(t.ticket, None)
                            
                        
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
                                await broadcast({"type": "log.event", "level": "INFO", "component": "smart_tp", "message": e.message, "created_at": datetime.now(pytz.utc).isoformat()})
                                continue
                                
                        cfg = await get_config()
                        current_dist = p['price_current'] - t.entry_price if p['type'] == mt5.ORDER_TYPE_BUY else t.entry_price - p['price_current']
                        tp_dist = abs(t.tp - t.entry_price) if t.tp else 0
                        
                        info = mt5.symbol_info(t.symbol)
                        digits = info.digits if info else 5
                        new_sl = None
                        
                        if tp_dist > 0:
                            # 1. Breakeven Logic
                            be_r = float(cfg.get("breakeven_trigger_r", 1.0))
                            reward_ratio = float(cfg.get("reward_ratio", 2.0))
                            estimated_risk = tp_dist / reward_ratio
                            
                            if be_r > 0 and estimated_risk > 0 and current_dist >= (estimated_risk * be_r):
                                tick = mt5.symbol_info_tick(t.symbol)
                                spread_buffer = (tick.ask - tick.bid) if tick else (info.point * 15)
                                
                                if "JPY" in t.symbol:
                                    pip_size = 0.01
                                elif digits in [3, 5]:
                                    pip_size = info.point * 10
                                else:
                                    pip_size = info.point
                                    
                                commission_buffer = pip_size * 0.5
                                be_buffer = spread_buffer + commission_buffer
                                
                                if p['type'] == mt5.ORDER_TYPE_BUY:
                                    be_price = t.entry_price + be_buffer
                                    if not t.sl or t.sl < be_price:
                                        new_sl = round(be_price, digits)
                                else:
                                    be_price = t.entry_price - be_buffer
                                    if not t.sl or t.sl > be_price:
                                        new_sl = round(be_price, digits)
                            
                            # 2. Trailing Stop (Starts at 70% of TP)
                            if cfg.get("trailing", True) and current_dist >= (tp_dist * 0.7):
                                if info:
                                    # Fetch recent ATR for volatility-aware trailing distance
                                    df_trail = await mt5_client.get_rates(t.symbol, mt5.TIMEFRAME_M15, 14)
                                    if not df_trail.empty:
                                        df_copy = df_trail.copy()
                                        df_copy['tr'] = pd.concat([
                                            df_copy['high'] - df_copy['low'],
                                            abs(df_copy['high'] - df_copy['close'].shift(1)),
                                            abs(df_copy['low'] - df_copy['close'].shift(1))
                                        ], axis=1).max(axis=1)
                                        atr_trail = df_copy['tr'].ewm(alpha=1/14, adjust=False).mean().iloc[-1]
                                        dist_points = atr_trail * 1.5
                                        
                                        if p['type'] == mt5.ORDER_TYPE_BUY:
                                            pot_sl = p['price_current'] - dist_points
                                            if pot_sl > t.entry_price and (not t.sl or pot_sl > t.sl) and (not new_sl or pot_sl > new_sl):
                                                new_sl = round(pot_sl, digits)
                                        else:
                                            pot_sl = p['price_current'] + dist_points
                                            if pot_sl < t.entry_price and (not t.sl or pot_sl < t.sl) and (not new_sl or pot_sl < new_sl):
                                                new_sl = round(pot_sl, digits)
                                            
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
        except Exception as e:
            print("Monitor error:", e)
            
        await asyncio.sleep(0.2)
