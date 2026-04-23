from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import TradeRecord

@ui.refreshable
def trades_table():
    db = SessionLocal()
    # closed trades
    trades = db.query(TradeRecord).filter(TradeRecord.closed_at.isnot(None)).order_by(TradeRecord.opened_at.desc()).limit(100).all()
    rows = []
    for t in trades:
        rows.append({
            'ticket': t.ticket,
            'symbol': t.symbol,
            'direction': t.direction,
            'lot': t.lot,
            'entry': t.entry_price,
            'exit': t.exit_price,
            'pnl': t.pnl,
            'opened': str(t.opened_at) if t.opened_at else '',
            'closed': str(t.closed_at) if t.closed_at else ''
        })
    db.close()
    
    cols = [
        {'name': 'ticket', 'label': 'Ticket', 'field': 'ticket'},
        {'name': 'symbol', 'label': 'Symbol', 'field': 'symbol'},
        {'name': 'direction', 'label': 'Dir', 'field': 'direction'},
        {'name': 'lot', 'label': 'Lot', 'field': 'lot'},
        {'name': 'entry', 'label': 'Entry', 'field': 'entry'},
        {'name': 'exit', 'label': 'Exit', 'field': 'exit'},
        {'name': 'pnl', 'label': 'PnL', 'field': 'pnl'},
        {'name': 'opened', 'label': 'Opened', 'field': 'opened'},
        {'name': 'closed', 'label': 'Closed', 'field': 'closed'},
    ]
    ui.table(columns=cols, rows=rows, row_key='ticket').classes('w-full bg-slate-900 mt-4')

def render():
    ui.label('Trade History').classes('text-2xl font-bold mb-4')
    trades_table()
    ui.timer(5.0, lambda: trades_table.refresh())
