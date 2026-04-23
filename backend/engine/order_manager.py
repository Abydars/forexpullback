import asyncio
from datetime import datetime
from backend.db.session import SessionLocal
from backend.db.models import Signal, Trade
from backend.mt5_client.client import mt5_client
from backend.core.config import config_manager
from backend.core.state import engine_state
from backend.core.logging import log_event
from backend.ws.manager import ws_manager

async def process_signal(signal_id: int):
    with SessionLocal() as db:
        signal = db.query(Signal).filter(Signal.id == signal_id).first()
        if not signal:
            return
            
        try:
            if not mt5_client.is_connected():
                signal.status = "FAILED"
                db.commit()
                log_event("warn", "order_manager", "MT5 not connected, skipping signal", {"signal_id": signal.id})
                return
                
            positions = mt5_client.get_positions()
            engine_state.open_positions_count = len(positions)
            
            if len(positions) >= config_manager.get("max_open_positions", 3):
                signal.status = "FAILED"
                db.commit()
                log_event("warn", "order_manager", "Max open positions reached", {"signal_id": signal.id})
                return
                
            account_info = mt5_client.account_info()
            if not account_info:
                signal.status = "FAILED"
                db.commit()
                return
                
            # Simplified sizing
            risk_pct = config_manager.get("risk_percent", 1.0)
            lot = 0.01 # Mock calculated lot
            
            # Send order
            request = {
                "action": 1, # mt5.TRADE_ACTION_DEAL
                "symbol": signal.symbol,
                "volume": lot,
                "type": 0 if signal.direction == "bullish" else 1, # 0=BUY, 1=SELL
                "price": signal.entry,
                "sl": signal.sl,
                "tp": signal.tp,
                "deviation": 20,
                "magic": 123456,
                "comment": "pullback_bot",
                "type_time": 0, # mt5.ORDER_TIME_GTC
                "type_filling": 1 # mt5.ORDER_FILLING_IOC
            }
            
            result = mt5_client.order_send(request)
            
            if result and getattr(result, "retcode", 0) == 10009: # DONE
                signal.status = "EXECUTED"
                
                trade = Trade(
                    signal_id=signal.id,
                    ticket=getattr(result, "order", 12345),
                    symbol=signal.symbol,
                    direction=signal.direction,
                    lot=lot,
                    entry_price=getattr(result, "price", signal.entry),
                    sl=signal.sl,
                    tp=signal.tp,
                    opened_at=datetime.utcnow()
                )
                db.add(trade)
                db.commit()
                db.refresh(trade)
                
                # Push trade
                await ws_manager.broadcast("trade.opened", {
                    "id": trade.id,
                    "ticket": trade.ticket,
                    "symbol": trade.symbol,
                    "direction": trade.direction,
                    "lot": trade.lot,
                    "entry_price": trade.entry_price
                })
                log_event("info", "order_manager", f"Trade opened for {signal.symbol}", {"ticket": trade.ticket})
            else:
                signal.status = "FAILED"
                db.commit()
                log_event("error", "order_manager", "Order send failed", {"signal_id": signal.id, "result": str(result)})
                
        except Exception as e:
            signal.status = "FAILED"
            db.commit()
            log_event("error", "order_manager", f"Exception processing signal: {e}")
