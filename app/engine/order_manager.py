import asyncio
import MetaTrader5 as mt5
import logging
from datetime import datetime
from app.core.config import cfg
from app.mt5_client.client import mt5_client
from app.db.models import TradeRecord

logger = logging.getLogger("order_manager")

async def execute_trade(signal, db):
    if not mt5_client.is_connected():
        return
        
    symbol = signal.symbol
    info = await asyncio.to_thread(mt5.symbol_info, symbol)
    if not info: return
    
    account_info = await mt5_client.account_info()
    balance = account_info['balance']
    
    sl_pips = abs(signal.entry - signal.sl) / info.point
    pip_value = info.trade_tick_value / info.trade_tick_size * info.point
    
    if sl_pips == 0 or pip_value == 0: return
    
    risk_amount = balance * (cfg.risk_percent / 100)
    lot_size = risk_amount / (sl_pips * pip_value)
    
    # clamp lot size
    lot = max(info.volume_min, min(info.volume_max, round(lot_size / info.volume_step) * info.volume_step))
    
    order_type = mt5.ORDER_TYPE_BUY if signal.direction == 'bullish' else mt5.ORDER_TYPE_SELL
    price = info.ask if order_type == mt5.ORDER_TYPE_BUY else info.bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": price,
        "sl": signal.sl,
        "tp": signal.tp,
        "deviation": 20,
        "magic": 123456,
        "comment": f"Sig_{signal.id}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    try:
        result = await mt5_client.order_send(request)
        if result['retcode'] == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Order executed: {result['order']}")
            trade = TradeRecord(
                signal_id=signal.id,
                ticket=result['order'],
                symbol=symbol,
                direction=signal.direction,
                lot=lot,
                entry_price=result['price'],
                sl=signal.sl,
                tp=signal.tp,
                opened_at=datetime.utcnow()
            )
            db.add(trade)
            db.commit()
            signal.status = 'executed'
        else:
            logger.error(f"Order failed: {result}")
            signal.status = 'failed'
            db.commit()
    except Exception as e:
        logger.error(f"Order send exception: {e}")
        signal.status = 'failed'
        db.commit()
