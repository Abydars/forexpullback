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
        positions = await mt5_client.get_positions()
        if len(positions) >= int(cfg.get("max_open_positions", 5)):
            return
            
        sym_pos = [p for p in positions if p['symbol'] == resolved]
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
        lot = max(info.volume_min, min(info.volume_max, round(lot / info.volume_step) * info.volume_step))
        
        action = mt5.TRADE_ACTION_DEAL
        type_ = mt5.ORDER_TYPE_BUY if bias == 'bullish' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": action,
            "symbol": resolved,
            "volume": float(lot),
            "type": type_,
            "price": mt5.symbol_info_tick(resolved).ask if type_ == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(resolved).bid,
            "sl": sig.sl,
            "tp": sig.tp,
            "deviation": 20,
            "magic": 123456,
            "comment": f"Sig {sig.id}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
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
                e = Event(level="ERROR", component="order_manager", message=f"Order failed: {res.get('comment', 'Unknown')}")
                db.add(e)
                await db.commit()
    except Exception as e:
        print("Order manager error:", e)
