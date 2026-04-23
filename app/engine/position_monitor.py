import asyncio
import MetaTrader5 as mt5
from app.mt5_client.client import mt5_client
from app.db.session import AsyncSessionLocal
from app.db.models import Trade
from sqlalchemy import select
from app.ws.manager import broadcast
from datetime import datetime
import pytz

async def monitor_loop():
    while True:
        from app.core.state import state
        if not state.engine_running or not mt5_client.is_connected():
            await asyncio.sleep(2)
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
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Trade).where(Trade.closed_at == None))
                open_trades = result.scalars().all()
                
                for t in open_trades:
                    if t.ticket not in pos_dict:
                        def _get_hist():
                            return mt5.history_deals_get(position=t.ticket)
                        history = await asyncio.to_thread(_get_hist)
                        if history:
                            exit_deal = history[-1]
                            t.closed_at = datetime.now(pytz.utc)
                            t.exit_price = exit_deal.price
                            t.pnl = exit_deal.profit
                            t.commission = exit_deal.commission
                            t.swap = exit_deal.swap
                            
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
                        await broadcast({
                            "type": "trade.updated",
                            "trade": {
                                "ticket": t.ticket, "symbol": t.symbol, "direction": t.direction,
                                "lot": t.lot, "entry_price": t.entry_price, "current_price": p['price_current'],
                                "pnl": p['profit'], "sl": t.sl, "tp": t.tp
                            }
                        })
        except Exception as e:
            print("Monitor error:", e)
            
        await asyncio.sleep(2)
