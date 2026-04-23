import asyncio
import MetaTrader5 as mt5
from app.mt5_client.client import mt5_client
from app.db.session import AsyncSessionLocal
from app.db.models import Trade, Event
from datetime import datetime
from app.ws.manager import broadcast
import pytz

async def send_order(sig, resolved: str, bias: str, cfg: dict):
    try:
        magic = int(cfg.get("magic_number", 123456))
        positions = await mt5_client.get_positions()
        
        bot_positions = [p for p in positions if p.get('magic') == magic]
        
        if len(bot_positions) >= int(cfg.get("max_open_positions", 5)):
            return
            
        sym_pos = [p for p in bot_positions if p['symbol'] == resolved]
        if len(sym_pos) >= int(cfg.get("max_per_symbol", 1)):
            return
            
        dir_type = 0 if bias == 'bullish' else 1
        sym_dir_pos = [p for p in sym_pos if p['type'] == dir_type]
        if len(sym_dir_pos) >= int(cfg.get("max_per_direction", 3)):
            return
            
        acc = await mt5_client.account_info()
        balance = acc['balance']
        
        info = mt5.symbol_info(resolved)
        if not info: return
        
        risk_pct = float(cfg.get("risk_percent", 1.0))
        sl_points = abs(sig.entry - sig.sl) / info.point if info.point else 1
        
        lot = (balance * risk_pct / 100) / (sl_points * info.trade_tick_value) if info.trade_tick_value else info.volume_min
        
        # precise volume calculation to prevent MT5 invalid volume errors
        steps = round(lot / info.volume_step)
        lot = steps * info.volume_step
        lot = max(info.volume_min, min(info.volume_max, lot))
        lot = float(f"{lot:.8f}".rstrip('0').rstrip('.')) if '.' in f"{lot:.8f}" else float(lot)
        
        action = mt5.TRADE_ACTION_DEAL
        type_ = mt5.ORDER_TYPE_BUY if bias == 'bullish' else mt5.ORDER_TYPE_SELL
        
        # dynamically determine correct filling mode based on broker/symbol limits
        filling_type = mt5.ORDER_FILLING_IOC
        if info.filling_mode & 1:
            filling_type = mt5.ORDER_FILLING_FOK
        elif info.filling_mode & 2:
            filling_type = mt5.ORDER_FILLING_IOC
        else:
            filling_type = mt5.ORDER_FILLING_RETURN
        
        request = {
            "action": action,
            "symbol": resolved,
            "volume": float(lot),
            "type": type_,
            "price": mt5.symbol_info_tick(resolved).ask if type_ == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(resolved).bid,
            "sl": sig.sl,
            "tp": sig.tp,
            "deviation": 20,
            "magic": magic,
            "comment": f"Sig {sig.id}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }
        
        res = await mt5_client.order_send(request)
        if res.get('retcode') == mt5.TRADE_RETCODE_DONE:
            ticket = res.get('order')
            async with AsyncSessionLocal() as db:
                t = Trade(signal_id=sig.id, ticket=ticket, symbol=resolved, direction=bias,
                         lot=lot, entry_price=res.get('price'), sl=sig.sl, tp=sig.tp,
                         opened_at=datetime.now(pytz.utc))
                db.add(t)
                await db.commit()
                await db.refresh(t)
                
                await broadcast({
                    "type": "trade.opened",
                    "trade": {
                        "ticket": ticket, "symbol": resolved, "direction": bias,
                        "lot": lot, "entry_price": t.entry_price, "sl": t.sl, "tp": t.tp,
                        "pnl": 0.0, "opened_at": t.opened_at.isoformat()
                    }
                })
        else:
            async with AsyncSessionLocal() as db:
                err_msg = f"Order rejected (Retcode {res.get('retcode')}): {res.get('comment', 'Unknown')}"
                e = Event(level="ERROR", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({
                    "type": "log.event", "level": "ERROR", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()
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
