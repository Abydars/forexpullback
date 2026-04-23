from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import TradeRecord

@ui.refreshable
def trades_table():
    db = SessionLocal()
    trades = db.query(TradeRecord).filter(TradeRecord.closed_at.isnot(None)).order_by(TradeRecord.opened_at.desc()).limit(50).all()
    rows = []
    for t in trades:
        pnl_val = t.pnl or 0.0
        pnl_str = f"{pnl_val:+.2f}"
        rows.append({
            'ticket': t.ticket,
            'symbol': t.symbol,
            'direction': 'LONG' if t.direction == 'bullish' else 'SHRT',
            'lot': f"{t.lot:.2f}",
            'pnl': pnl_str,
            'pnl_color': 'text-green-500' if pnl_val >= 0 else 'text-red-500',
            'closed': t.closed_at.strftime('%H:%M:%S') if t.closed_at else ''
        })
    db.close()
    
    with ui.column().classes('w-full gap-0 text-[9px] font-mono'):
        # Header
        with ui.row().classes('w-full items-center justify-between px-2 py-1 text-neutral-500 border-b border-[#1a1a1a]'):
            ui.label('SYM').classes('w-10')
            ui.label('DIR').classes('w-8')
            ui.label('LOT').classes('w-8 text-right')
            ui.label('PNL').classes('w-10 text-right')
            ui.label('TIME').classes('w-12 text-right')
            
        # Rows
        for r in rows:
            with ui.row().classes('w-full items-center justify-between px-2 py-1 border-b border-[#111] hover:bg-[#111]'):
                ui.label(r['symbol']).classes('w-10 text-neutral-300 font-bold')
                col = 'text-green-500' if r['direction'] == 'LONG' else 'text-red-500'
                ui.label(r['direction']).classes(f'w-8 {col}')
                ui.label(r['lot']).classes('w-8 text-right text-neutral-400')
                ui.label(r['pnl']).classes(f"w-10 text-right font-bold {r['pnl_color']}")
                ui.label(r['closed']).classes('w-12 text-right text-neutral-600')

def render_trades():
    with ui.element('div').classes('flex-grow overflow-auto bg-transparent'):
        trades_table()
    ui.timer(5.0, lambda: trades_table.refresh())
