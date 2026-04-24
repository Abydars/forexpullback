import asyncio
from app.binance_client.client import binance_client
from app.binance_client.symbol_resolver import SymbolResolver
from app.db.session import AsyncSessionLocal
from app.db.models import Trade, Event
from datetime import datetime
from app.ws.manager import broadcast
from sqlalchemy import select
import pytz
import time

resolver = SymbolResolver(binance_client)

async def send_order(sig, resolved: str, bias: str, cfg: dict, is_dca=False, dca_data=None):
    try:
        positions = await binance_client.get_positions()
        
        # We only track our bot's positions using DB, but we can also limit total open positions
        # Let's count open positions from DB for active tracking
        async with AsyncSessionLocal() as db:
            active_trades = await db.execute(select(Trade).where(Trade.closed_at == None))
            bot_positions = active_trades.scalars().all()
            
            if len(bot_positions) >= int(cfg.get("max_open_positions", 5)):
                return
                
            if not is_dca:
                sym_pos = [p for p in bot_positions if p.symbol == resolved]
                if len(sym_pos) >= int(cfg.get("max_per_symbol", 1)):
                    return
                    
                sym_dir_pos = [p for p in sym_pos if p.direction == bias]
                if len(sym_dir_pos) >= int(cfg.get("max_per_direction", 3)):
                    return
        
        acc = await binance_client.account_info()
        balance = float(acc.get('totalWalletBalance', 0.0))
        
        info = binance_client.symbol_info(resolved)
        if not info: return
        
        tick = await binance_client.symbol_info_tick(resolved)
        if not tick: return
        actual_price = tick['ask'] if bias == 'bullish' else tick['bid']
        
        # Spread check
        spread = tick['ask'] - tick['bid']
        sl_distance = abs(actual_price - sig.sl)
        
        spread_pct = (spread / sl_distance) * 100 if sl_distance > 0 else 100
        max_spread_pct = float(cfg.get("max_spread_pct", 20.0))
        
        if spread_pct > max_spread_pct:
            async with AsyncSessionLocal() as db:
                err_msg = f"Order {resolved} rejected: Spread is {spread_pct:.1f}% of SL distance (Max allowed: {max_spread_pct}%)"
                e = Event(level="WARN", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({"type": "log.event", "level": "WARN", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()})
            return
            
        risk_pct = float(cfg.get("risk_percent", 1.0))
        risk_amount = balance * risk_pct / 100
        
        if is_dca and dca_data:
            qty = dca_data.get('dca_lot', 0)
        else:
            if sl_distance > 0:
                qty = risk_amount / sl_distance
            else:
                qty = 0
            
        qty = resolver.round_qty(resolved, qty)
        
        if qty <= 0:
            return
            
        # Optional: set leverage
        default_leverage = int(cfg.get("default_leverage", 10))
        await binance_client.set_leverage(resolved, default_leverage)
        
        # Optional: set margin type
        margin_type = cfg.get("margin_type", "ISOLATED").upper()
        await binance_client.set_margin_type(resolved, margin_type)
        
        side = 'BUY' if bias == 'bullish' else 'SELL'
        position_side = 'LONG' if bias == 'bullish' else 'SHORT'
        
        client_order_id = f"fpb_{sig.id}_{int(time.time() * 1000)}"
        if is_dca:
            client_order_id = f"fpb_dca_{sig.id}_{int(time.time() * 1000)}"
            
        # 1. Entry Order
        req = {
            'symbol': resolved,
            'side': side,
            'positionSide': position_side,
            'type': 'MARKET',
            'quantity': qty,
            'newClientOrderId': client_order_id
        }
        
        res = await binance_client.order_send(req)
        order_id = str(res.get('orderId'))
        entry_price = float(res.get('avgPrice', res.get('price', actual_price)))
        if entry_price == 0: entry_price = actual_price
        
        # 2. SL Order
        sl_side = 'SELL' if bias == 'bullish' else 'BUY'
        sl_req = {
            'algoType': 'CONDITIONAL',
            'symbol': resolved,
            'side': sl_side,
            'positionSide': position_side,
            'type': 'STOP_MARKET',
            'triggerPrice': resolver.round_price(resolved, sig.sl),
            'closePosition': 'TRUE'
        }
        sl_res = await binance_client.algo_order_send(sl_req)
        sl_order_id = str(sl_res.get('algoId'))
        
        # 3. TP Order
        tp_req = {
            'algoType': 'CONDITIONAL',
            'symbol': resolved,
            'side': sl_side,
            'positionSide': position_side,
            'type': 'TAKE_PROFIT_MARKET',
            'triggerPrice': resolver.round_price(resolved, sig.tp),
            'closePosition': 'TRUE'
        }
        tp_res = await binance_client.algo_order_send(tp_req)
        tp_order_id = str(tp_res.get('algoId'))
        
        async with AsyncSessionLocal() as db:
            t = Trade(signal_id=sig.id, symbol=resolved, direction=bias,
                      quantity=qty, entry_price=entry_price, sl=sig.sl, tp=sig.tp,
                      opened_at=datetime.now(pytz.utc), exchange='binance',
                      order_id=order_id, client_order_id=client_order_id,
                      position_side=position_side, sl_order_id=sl_order_id, tp_order_id=tp_order_id)
            
            if is_dca and dca_data:
                t.parent_trade_id = dca_data.get('parent_ticket')
                t.dca_index = dca_data.get('dca_index', 0)
                t.group_id = f"grp_{t.parent_trade_id}"
                t.note = f"DCA #{t.dca_index}"
            else:
                t.note = "BASE"
                t.group_id = f"grp_{order_id}"

            db.add(t)
            await db.commit()
            await db.refresh(t)
            
            # Reanchor SL for existing DCA positions
            if is_dca and dca_data:
                reanchor_sl = cfg.get("dca_reanchor_sl", True)
                if reanchor_sl:
                    active_same = await db.execute(select(Trade).where(
                        Trade.closed_at == None, Trade.symbol == resolved, Trade.direction == bias
                    ))
                    same_trades = active_same.scalars().all()
                    
                    for p in same_trades:
                        if p.id == t.id: continue
                        
                        # Cancel old SL
                        if p.sl_order_id:
                            try:
                                await binance_client.algo_order_cancel(resolved, order_id=p.sl_order_id)
                            except:
                                pass
                                
                        # Cancel old TP
                        if p.tp_order_id:
                            try:
                                await binance_client.algo_order_cancel(resolved, order_id=p.tp_order_id)
                            except:
                                pass
                        
                        # Place new SL/TP
                        try:
                            nsl_res = await binance_client.algo_order_send(sl_req)
                            p.sl_order_id = str(nsl_res.get('algoId'))
                            p.sl = sig.sl
                            
                            ntp_res = await binance_client.algo_order_send(tp_req)
                            p.tp_order_id = str(ntp_res.get('algoId'))
                            p.tp = sig.tp
                        except Exception as e:
                            print("Reanchor error:", e)
                    
                    await db.commit()
            
            await broadcast({
                "type": "trade.opened",
                "trade": {
                    "id": t.id, "symbol": resolved, "direction": bias,
                    "quantity": qty, "entry_price": t.entry_price, "sl": t.sl, "tp": t.tp,
                    "pnl": 0.0, "opened_at": t.opened_at.isoformat()
                }
            })

    except Exception as e:
        print("Order manager error:", e)
        err_msg = f"Order exception: {str(e)}"
        try:
            async with AsyncSessionLocal() as db:
                ev = Event(level="ERROR", component="order_manager", message=err_msg)
                db.add(ev)
                await db.commit()
                await broadcast({
                    "type": "log.event", "level": "ERROR", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()
                })
        except:
            pass
