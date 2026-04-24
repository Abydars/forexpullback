import asyncio
from app.binance_client.client import binance_client
from app.binance_client.symbol_resolver import SymbolResolver
from app.db.session import AsyncSessionLocal
from app.db.models import Trade, Event
from sqlalchemy import select
from app.ws.manager import broadcast
from datetime import datetime
import pytz
import pandas as pd
from app.core.config import get_config

resolver = SymbolResolver(binance_client)

async def evaluate_smart_exit(p: dict, t: Trade, symbol: str) -> str | None:
    unrealized_pnl = float(p.get('unRealizedProfit', 0))
    if unrealized_pnl <= 0:
        return None
        
    opened_at = t.opened_at
    if opened_at.tzinfo is None: opened_at = opened_at.replace(tzinfo=pytz.utc)
    if (datetime.now(pytz.utc) - opened_at).total_seconds() < 20 * 60:
        return None
        
    df = await binance_client.get_rates(symbol, 'M5', 15)
    if df.empty or len(df) < 15: return None
    
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
    
    if t.direction == 'bullish':
        if tp and tp > entry:
            tp_dist = tp - entry
            max_reached = max(last['high'], prev['high']) - entry
            if max_reached >= tp_dist * 0.8:
                if (last['close'] - entry) <= tp_dist * 0.6:
                    return "Smart TP: Closed below 60% after reaching 80%"
                    
        if last['close'] < last['open'] and last['close'] < prev['low']:
            move_size = entry - last['close'] if entry > last['close'] else last['close'] - entry
            if move_size > (0.5 * atr):
                if is_strong or (prev['close'] < prev['open']):
                    return "Smart TP: Strong Bearish Reversal Detected"
    else:
        if tp and tp < entry:
            tp_dist = entry - tp
            max_reached = entry - min(last['low'], prev['low'])
            if max_reached >= tp_dist * 0.8:
                if (entry - last['close']) <= tp_dist * 0.6:
                    return "Smart TP: Closed below 60% after reaching 80%"
                    
        if last['close'] > last['open'] and last['close'] > prev['high']:
            move_size = last['close'] - entry if last['close'] > entry else entry - last['close']
            if move_size > (0.5 * atr):
                if is_strong or (prev['close'] > prev['open']):
                    return "Smart TP: Strong Bullish Reversal Detected"
                
    return None

async def close_trade_binance(t: Trade):
    # Cancel SL/TP
    if t.sl_order_id:
        try:
            await binance_client.order_cancel(t.symbol, order_id=t.sl_order_id)
        except: pass
    if t.tp_order_id:
        try:
            await binance_client.order_cancel(t.symbol, order_id=t.tp_order_id)
        except: pass

    # Market close
    req = {
        'symbol': t.symbol,
        'side': 'SELL' if t.direction == 'bullish' else 'BUY',
        'positionSide': t.position_side,
        'type': 'MARKET',
        'quantity': t.quantity,
    }
    try:
        await binance_client.order_send(req)
        return True
    except Exception as e:
        print(f"Close error {t.symbol}: {e}")
        return False

basket_state = {"active": False, "peak_pnl": 0.0}

async def monitor_loop():
    global basket_state
    retry_counts = {}
    while True:
        from app.core.state import state
        if not binance_client.is_connected():
            await asyncio.sleep(2)
            continue
            
        try:
            positions = await binance_client.get_positions()
            acc = await binance_client.account_info()
            if acc:
                balance = float(acc.get('totalWalletBalance', 0))
                equity = float(acc.get('totalMarginBalance', 0))
                margin = float(acc.get('totalPositionInitialMargin', 0))
                await broadcast({
                    "type": "account.tick",
                    "balance": balance,
                    "equity": equity,
                    "margin": margin,
                    "currency": "USDT"
                })
            
            # Normalize binance positions for broadcast matching old MT5 format
            norm_positions = []
            for p in positions:
                sym = p['symbol']
                qty = abs(float(p['positionAmt']))
                side = 0 if p['positionSide'] == 'LONG' else 1
                unrealized = float(p['unRealizedProfit'])
                entry_price = float(p['entryPrice'])
                mark_price = float(p['markPrice'])
                
                norm_positions.append({
                    'symbol': sym,
                    'type': side,
                    'volume': qty,
                    'price_open': entry_price,
                    'price_current': mark_price,
                    'profit': unrealized,
                    'positionSide': p['positionSide']
                })
                
            cfg = await get_config()
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Trade).where(Trade.closed_at == None))
                open_trades = result.scalars().all()
                
                bot_positions = []
                for t in open_trades:
                    # Match with binance positions
                    found = False
                    for np in norm_positions:
                        if np['symbol'] == t.symbol and np['positionSide'] == t.position_side:
                            bot_positions.append(np)
                            found = True
                            break
                            
                    if not found:
                        # Position closed
                        t.closed_at = datetime.now(pytz.utc)
                        # Here we could fetch exit price from trades history, but for simplicity:
                        t.exit_price = t.entry_price # Default if we don't fetch trade history
                        t.pnl = 0.0
                        t.commission = 0.0
                        
                        await broadcast({
                            "type": "trade.closed",
                            "trade": {
                                "id": t.id, "symbol": t.symbol, "direction": t.direction,
                                "quantity": t.quantity, "entry_price": t.entry_price, "exit_price": t.exit_price,
                                "pnl": t.pnl, "sl": t.sl, "tp": t.tp
                            }
                        })
                    else:
                        # Position still open
                        p = next((x for x in positions if x['symbol'] == t.symbol and x['positionSide'] == t.position_side), None)
                        if not p: continue
                        
                        unrealized = float(p['unRealizedProfit'])
                        mark_price = float(p['markPrice'])
                        
                        exit_reason = await evaluate_smart_exit(p, t, t.symbol)
                        if exit_reason:
                            success = await close_trade_binance(t)
                            if success:
                                e = Event(level="INFO", component="smart_tp", message=f"Closed {t.symbol}: {exit_reason} at +${unrealized:.2f}")
                                db.add(e)
                                await broadcast({"type": "log.event", "level": "INFO", "component": "smart_tp", "message": e.message, "created_at": datetime.now(pytz.utc).isoformat()})
                                continue
                                
                        current_dist = mark_price - t.entry_price if t.direction == 'bullish' else t.entry_price - mark_price
                        tp_dist = abs(t.tp - t.entry_price) if t.tp else 0
                        new_sl = None
                        
                        if tp_dist > 0:
                            be_r = float(cfg.get("breakeven_trigger_r", 1.0))
                            reward_ratio = float(cfg.get("reward_ratio", 2.0))
                            estimated_risk = tp_dist / reward_ratio
                            
                            if be_r > 0 and estimated_risk > 0 and current_dist >= (estimated_risk * be_r):
                                be_buffer = t.entry_price * 0.001 # rough fee buffer
                                if t.direction == 'bullish':
                                    be_price = t.entry_price + be_buffer
                                    if not t.sl or t.sl < be_price:
                                        new_sl = resolver.round_price(t.symbol, be_price)
                                else:
                                    be_price = t.entry_price - be_buffer
                                    if not t.sl or t.sl > be_price:
                                        new_sl = resolver.round_price(t.symbol, be_price)
                                        
                            if cfg.get("trailing", True) and current_dist >= (tp_dist * 0.7):
                                df_trail = await binance_client.get_rates(t.symbol, 'M15', 14)
                                if not df_trail.empty:
                                    df_copy = df_trail.copy()
                                    df_copy['tr'] = pd.concat([
                                        df_copy['high'] - df_copy['low'],
                                        abs(df_copy['high'] - df_copy['close'].shift(1)),
                                        abs(df_copy['low'] - df_copy['close'].shift(1))
                                    ], axis=1).max(axis=1)
                                    atr_trail = df_copy['tr'].ewm(alpha=1/14, adjust=False).mean().iloc[-1]
                                    dist_points = atr_trail * 1.5
                                    
                                    if t.direction == 'bullish':
                                        pot_sl = mark_price - dist_points
                                        if pot_sl > t.entry_price and (not t.sl or pot_sl > t.sl) and (not new_sl or pot_sl > new_sl):
                                            new_sl = resolver.round_price(t.symbol, pot_sl)
                                    else:
                                        pot_sl = mark_price + dist_points
                                        if pot_sl < t.entry_price and (not t.sl or pot_sl < t.sl) and (not new_sl or pot_sl < new_sl):
                                            new_sl = resolver.round_price(t.symbol, pot_sl)
                                            
                        if new_sl:
                            try:
                                if t.sl_order_id:
                                    await binance_client.order_cancel(t.symbol, order_id=t.sl_order_id)
                                    
                                sl_side = 'SELL' if t.direction == 'bullish' else 'BUY'
                                sl_req = {
                                    'symbol': t.symbol,
                                    'side': sl_side,
                                    'positionSide': t.position_side,
                                    'type': 'STOP_MARKET',
                                    'stopPrice': new_sl,
                                    'closePosition': 'true',
                                    'timeInForce': 'GTC'
                                }
                                nsl_res = await binance_client.order_send(sl_req)
                                t.sl_order_id = str(nsl_res.get('orderId'))
                                t.sl = new_sl
                            except Exception as e:
                                print(f"Trailing SL update failed for {t.symbol}: {e}")
                
                # Basket logic
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
                            db.add(Event(level="INFO", component="basket", message=msg))
                            await broadcast({"type": "log.event", "level": "INFO", "component": "basket", "message": msg, "created_at": datetime.now(pytz.utc).isoformat()})
                        else:
                            if total_unrealized_pnl > basket_state["peak_pnl"]:
                                basket_state["peak_pnl"] = total_unrealized_pnl
                    
                    if basket_state["active"]:
                        if total_unrealized_pnl < min_close_usd:
                            msg = f"Basket trailing reset: PnL dropped below minimum close profit (Peak was +${basket_state['peak_pnl']:.2f})"
                            basket_state["active"] = False
                            basket_state["peak_pnl"] = 0.0
                            db.add(Event(level="INFO", component="basket", message=msg))
                            await broadcast({"type": "log.event", "level": "INFO", "component": "basket", "message": msg, "created_at": datetime.now(pytz.utc).isoformat()})
                        elif basket_state["peak_pnl"] - total_unrealized_pnl >= drawdown_usd:
                            for t in open_trades:
                                await close_trade_binance(t)
                                
                            msg = f"Basket trailing close: secured +${total_unrealized_pnl:.2f} minimum basket profit (Peak: +${basket_state['peak_pnl']:.2f})"
                            db.add(Event(level="INFO", component="basket", message=msg))
                            await broadcast({"type": "log.event", "level": "INFO", "component": "basket", "message": msg, "created_at": datetime.now(pytz.utc).isoformat()})
                            basket_state["active"] = False
                            basket_state["peak_pnl"] = 0.0
                else:
                    basket_state["active"] = False
                    basket_state["peak_pnl"] = 0.0
                
                await db.commit()

            await broadcast({
                "type": "positions.update",
                "positions": norm_positions,
                "basket_state": basket_state
            })
                
        except Exception as e:
            print("Monitor error:", e)
            
        await asyncio.sleep(1)
