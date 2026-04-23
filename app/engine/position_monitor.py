import asyncio
from datetime import datetime, timezone
import MetaTrader5 as mt5
from app.ui.state import state
from app.mt5_client.client import mt5_client
from app.db.session import SessionLocal
from app.db.models import TradeRecord, SessionRecord
from app.core.sessions import active_sessions

async def position_monitor_loop():
    while True:
        await asyncio.sleep(2.0)
        
        # Update active sessions in state
        db = SessionLocal()
        sessions = db.query(SessionRecord).all()
        db.close()
        
        active = active_sessions(sessions, datetime.now(timezone.utc))
        state.active_sessions = [s.name for s in active]
        
        if not mt5_client.is_connected():
            continue
            
        try:
            # Update account info
            acc = await mt5_client.account_info()
            state.account = acc
            state.equity_series.append((datetime.now().timestamp() * 1000, acc['equity']))
            if len(state.equity_series) > 1000:
                state.equity_series = state.equity_series[-1000:]
                
            # Update open positions
            positions = await mt5_client.get_positions()
            state.open_positions = positions
            
            # Check for closed positions to update trades DB
            # We compare DB open trades with current MT5 positions
            db = SessionLocal()
            open_db_trades = db.query(TradeRecord).filter_by(closed_at=None).all()
            pos_tickets = {p['ticket'] for p in positions}
            
            today_pnl = 0.0
            
            for t in open_db_trades:
                if t.ticket not in pos_tickets:
                    # Trade closed! Look up history in MT5
                    history = await asyncio.to_thread(mt5.history_deals_get, position=t.ticket)
                    if history:
                        close_deal = history[-1] # Usually the last deal is the close
                        t.closed_at = datetime.utcnow()
                        t.exit_price = close_deal.price
                        t.pnl = close_deal.profit
                        t.commission = close_deal.commission
                        t.swap = close_deal.swap
                        db.commit()
                        
            # Calc today's pnl roughly
            midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_trades = db.query(TradeRecord).filter(TradeRecord.closed_at >= midnight).all()
            today_pnl = sum(t.pnl or 0 for t in today_trades)
            
            # Add floating PnL
            floating_pnl = sum(p['profit'] for p in positions)
            state.today_pnl = today_pnl + floating_pnl
            
            db.close()
        except Exception as e:
            state.last_error = str(e)
