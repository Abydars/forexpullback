from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import TradeRecord

@ui.refreshable
def trades_table():
    db = SessionLocal()
    trades = db.query(TradeRecord).filter(TradeRecord.closed_at.isnot(None)).order_by(TradeRecord.opened_at.desc()).limit(100).all()
    rows = []
    for t in trades:
        rows.append({
            'ticket': t.ticket,
            'symbol': t.symbol,
            'direction': 'LONG' if t.direction == 'bullish' else 'SHORT',
            'lot': f"{t.lot:.2f}",
            'entry': f"{t.entry_price:.5f}",
            'exit': f"{t.exit_price:.5f}" if t.exit_price else "",
            'pnl': f"{t.pnl:.2f}" if t.pnl else "0.00",
            'opened': t.opened_at.strftime('%m-%d %H:%M') if t.opened_at else '',
            'closed': t.closed_at.strftime('%m-%d %H:%M') if t.closed_at else ''
        })
    db.close()
    
    cols = [
        {'name': 'ticket', 'label': 'ID', 'field': 'ticket', 'align': 'left'},
        {'name': 'symbol', 'label': 'SYM', 'field': 'symbol', 'align': 'left'},
        {'name': 'direction', 'label': 'DIR', 'field': 'direction', 'align': 'left'},
        {'name': 'lot', 'label': 'LOT', 'field': 'lot', 'align': 'right'},
        {'name': 'entry', 'label': 'ENTRY', 'field': 'entry', 'align': 'right'},
        {'name': 'exit', 'label': 'EXIT', 'field': 'exit', 'align': 'right'},
        {'name': 'pnl', 'label': 'PNL', 'field': 'pnl', 'align': 'right'},
        {'name': 'opened', 'label': 'OPENED', 'field': 'opened', 'align': 'right'},
        {'name': 'closed', 'label': 'CLOSED', 'field': 'closed', 'align': 'right'},
    ]
    ui.table(columns=cols, rows=rows, row_key='ticket').props('dense flat bordered square dark').classes('w-full bg-[#0a0a0a] text-neutral-300 font-mono text-[10px]')

def render():
    ui.label('TRADE_HISTORY').classes('text-[10px] text-neutral-500 uppercase tracking-widest font-sans mb-2')
    trades_table()
    ui.timer(5.0, lambda: trades_table.refresh())
