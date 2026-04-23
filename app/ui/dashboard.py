from nicegui import ui
from app.ui.state import state

@ui.refreshable
def stat_cards():
    with ui.row().classes('w-full gap-4 mb-4'):
        acc = state.account or {}
        
        def card(title, value, color='text-slate-200'):
            with ui.card().classes('flex-1 bg-slate-900 border border-slate-800'):
                ui.label(title).classes('text-sm text-slate-400')
                ui.label(value).classes(f'text-2xl font-mono {color}')
                
        card('Balance', f"{acc.get('balance', 0):.2f}")
        card('Equity', f"{acc.get('equity', 0):.2f}")
        
        pnl_color = 'text-emerald-400' if state.today_pnl >= 0 else 'text-rose-400'
        card('Today PnL', f"{state.today_pnl:.2f}", pnl_color)
        
        card('Open Positions', str(len(state.open_positions)))

@ui.refreshable
def equity_chart():
    # nicegui echart wrapper
    opts = {
        'xAxis': {'type': 'time'},
        'yAxis': {'type': 'value', 'scale': True},
        'series': [{'type': 'line', 'data': state.equity_series, 'showSymbol': False}],
        'backgroundColor': 'transparent',
        'textStyle': {'color': '#94a3b8'}
    }
    ui.echart(opts).classes('w-full h-64 bg-slate-900 rounded border border-slate-800 p-2')

@ui.refreshable
def positions_table():
    cols = [
        {'name': 'ticket', 'label': 'Ticket', 'field': 'ticket'},
        {'name': 'symbol', 'label': 'Symbol', 'field': 'symbol'},
        {'name': 'type_str', 'label': 'Type', 'field': 'type_str'},
        {'name': 'volume', 'label': 'Lot', 'field': 'volume'},
        {'name': 'price_open', 'label': 'Entry', 'field': 'price_open'},
        {'name': 'sl', 'label': 'SL', 'field': 'sl'},
        {'name': 'tp', 'label': 'TP', 'field': 'tp'},
        {'name': 'profit', 'label': 'Profit', 'field': 'profit'},
    ]
    rows = [{**p, 'type_str': 'Buy' if p.get('type') == 0 else 'Sell'} for p in state.open_positions]
    ui.table(columns=cols, rows=rows, row_key='ticket').classes('w-full bg-slate-900 mt-4')

@ui.refreshable
def signals_feed():
    with ui.column().classes('w-full gap-2 mt-4'):
        ui.label('Recent Signals').classes('text-lg font-bold text-slate-200')
        for sig in state.recent_signals[:20]:
            with ui.card().classes('w-full bg-slate-800 p-2'):
                ui.label(f"{sig['symbol']} - {sig['direction']} (Score: {sig['score']})").classes('font-bold')

def render():
    stat_cards()
    with ui.row().classes('w-full gap-4'):
        with ui.column().classes('w-2/3'):
            equity_chart()
        with ui.column().classes('w-1/3'):
            signals_feed()
    positions_table()
    ui.timer(2.0, lambda: (stat_cards.refresh(), equity_chart.refresh(),
                           positions_table.refresh(), signals_feed.refresh()))
