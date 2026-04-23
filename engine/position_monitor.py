import asyncio
from datetime import datetime
from db.session import SessionLocal
from db.models import Trade
from mt5_client.client import mt5_client
from ws.manager import ws_manager
from core.state import engine_state
from core.logging import log_event

async def monitor_loop():
    while True:
        try:
            if not mt5_client.is_connected() or not engine_state.is_running:
                await asyncio.sleep(5)
                continue
                
            positions = mt5_client.get_positions()
            active_tickets = {p.ticket for p in positions} if positions else set()
            
            with SessionLocal() as db:
                open_trades = db.query(Trade).filter(Trade.closed_at == None).all()
                for trade in open_trades:
                    if trade.ticket not in active_tickets:
                        history = mt5_client.history_deals_get(ticket=trade.ticket)
                        if history:
                            exit_deal = history[-1]
                            trade.closed_at = datetime.utcnow()
                            trade.exit_price = getattr(exit_deal, "price", 0.0)
                            trade.pnl = getattr(exit_deal, "profit", 0.0)
                            trade.commission = getattr(exit_deal, "commission", 0.0)
                            trade.swap = getattr(exit_deal, "swap", 0.0)
                        else:
                            trade.closed_at = datetime.utcnow()
                            
                        db.commit()
                        await ws_manager.broadcast("trade.closed", {"ticket": trade.ticket})
                        log_event("info", "position_monitor", f"Trade {trade.ticket} closed")
                        
            account = mt5_client.account_info()
            if account:
                await ws_manager.broadcast("account.tick", {
                    "balance": account.balance,
                    "equity": account.equity,
                    "margin": account.margin
                })
                
        except Exception as e:
            log_event("error", "position_monitor", f"Exception in monitor loop: {e}")
            
        await asyncio.sleep(2)
