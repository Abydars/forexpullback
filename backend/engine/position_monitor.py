import asyncio
from datetime import datetime
from backend.db.session import SessionLocal
from backend.db.models import Trade
from backend.mt5_client.client import mt5_client
from backend.ws.manager import ws_manager
from backend.core.state import engine_state
from backend.core.logging import log_event

async def position_monitor_loop():
    while True:
        try:
            if not mt5_client.is_connected() or not engine_state.is_running:
                await asyncio.sleep(2)
                continue
                
            positions = mt5_client.get_positions()
            engine_state.open_positions_count = len(positions)
            
            open_tickets = {p.ticket for p in positions}
            
            with SessionLocal() as db:
                db_open_trades = db.query(Trade).filter(Trade.closed_at == None).all()
                for trade in db_open_trades:
                    if trade.ticket not in open_tickets:
                        # Trade was closed
                        # In reality we'd pull from history to get exact PnL, mock for now
                        trade.closed_at = datetime.utcnow()
                        trade.exit_price = trade.entry_price # mock
                        trade.pnl = 10.0 # mock
                        db.commit()
                        
                        await ws_manager.broadcast("trade.closed", {
                            "ticket": trade.ticket,
                            "pnl": trade.pnl
                        })
                        log_event("info", "position_monitor", f"Trade {trade.ticket} closed", {"pnl": trade.pnl})
                        
            # Broadcast account tick
            acc = mt5_client.account_info()
            if acc:
                await ws_manager.broadcast("account.tick", {
                    "balance": acc.balance,
                    "equity": acc.equity,
                    "margin": acc.margin
                })
                
            await asyncio.sleep(2)
            
        except Exception as e:
            log_event("error", "position_monitor", f"Monitor loop error: {e}")
            await asyncio.sleep(5)
