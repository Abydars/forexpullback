from nicegui import ui
from app.ui.state import state

@ui.refreshable
def account_summary():
    acc = state.account or {}
    with ui.row().classes('absolute top-2 left-2 z-10 gap-2'):
        def badge(lbl, val, col='text-neutral-200'):
            with ui.column().classes('bg-[#050505] border border-[#222] px-2 py-1 gap-0'):
                ui.label(lbl).classes('text-[8px] text-neutral-500 uppercase')
                ui.label(val).classes(f'text-sm font-bold {col}')
        
        badge('BALANCE', f"{acc.get('balance', 0):.2f}")
        badge('EQUITY', f"{acc.get('equity', 0):.2f}")
        pnl_col = 'text-green-500' if state.today_pnl >= 0 else 'text-red-500'
        badge('TODAY PNL', f"{state.today_pnl:+.2f}", pnl_col)

@ui.refreshable
def equity_chart():
    opts = {
        'grid': {'top': 10, 'right': 10, 'bottom': 20, 'left': 50},
        'xAxis': {'type': 'time', 'splitLine': {'show': True, 'lineStyle': {'color': '#111'}}, 'axisLabel': {'color': '#555', 'fontSize': 9}},
        'yAxis': {'type': 'value', 'scale': True, 'splitLine': {'show': True, 'lineStyle': {'color': '#111'}}, 'axisLabel': {'color': '#555', 'fontSize': 9}},
        'series': [{'type': 'line', 'data': state.equity_series, 'showSymbol': False, 'lineStyle': {'color': '#3b82f6', 'width': 1.5}}],
        'backgroundColor': 'transparent',
    }
    ui.echart(opts).classes('w-full h-full')

def render_chart():
    with ui.element('div').classes('relative w-full h-full'):
        account_summary()
        equity_chart()
    ui.timer(2.0, lambda: (account_summary.refresh(), equity_chart.refresh()))

@ui.refreshable
def positions_table():
    cols = [
        {'name': 'ticket', 'label': 'ID', 'field': 'ticket', 'align': 'left'},
        {'name': 'symbol', 'label': 'SYM', 'field': 'symbol', 'align': 'left'},
        {'name': 'type_str', 'label': 'DIR', 'field': 'type_str', 'align': 'left'},
        {'name': 'volume', 'label': 'LOT', 'field': 'volume', 'align': 'right'},
        {'name': 'price_open', 'label': 'ENTRY', 'field': 'price_open', 'align': 'right'},
        {'name': 'sl', 'label': 'SL', 'field': 'sl', 'align': 'right'},
        {'name': 'tp', 'label': 'TP', 'field': 'tp', 'align': 'right'},
        {'name': 'profit', 'label': 'PNL', 'field': 'profit', 'align': 'right'},
    ]
    rows = [{**p, 'type_str': 'BUY' if p.get('type') == 0 else 'SELL'} for p in state.open_positions]
    
    ui.table(columns=cols, rows=rows, row_key='ticket').props('dense flat bordered square dark hide-pagination').classes('w-full bg-transparent text-neutral-300 text-[10px]')

def render_positions():
    ui.label('OPEN PORTFOLIO').classes('text-[9px] text-neutral-500 bg-[#111] px-2 py-1 border-b border-[#222] w-full tracking-widest')
    with ui.element('div').classes('flex-grow overflow-auto'):
        positions_table()
    ui.timer(2.0, lambda: positions_table.refresh())
