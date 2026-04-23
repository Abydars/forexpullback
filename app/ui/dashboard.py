from nicegui import ui
from app.ui.state import state

@ui.refreshable
def stat_cards():
    with ui.row().classes('w-full gap-2 mb-2'):
        acc = state.account or {}
        
        def card(title, value, color='text-neutral-200'):
            with ui.column().classes('flex-1 bg-[#0a0a0a] border border-[#222] p-2 gap-0'):
                ui.label(title).classes('text-[10px] text-neutral-500 uppercase tracking-widest font-sans')
                ui.label(value).classes(f'text-lg font-mono {color}')
                
        card('BALANCE', f"{acc.get('balance', 0):.2f}")
        card('EQUITY', f"{acc.get('equity', 0):.2f}")
        
        pnl_color = 'text-green-500' if state.today_pnl >= 0 else 'text-red-500'
        card('TODAY PNL', f"{state.today_pnl:+.2f}", pnl_color)
        
        card('OPEN POS', str(len(state.open_positions)))

@ui.refreshable
def equity_chart():
    opts = {
        'grid': {'top': 10, 'right': 10, 'bottom': 20, 'left': 50},
        'xAxis': {'type': 'time', 'splitLine': {'show': True, 'lineStyle': {'color': '#111'}}, 'axisLabel': {'color': '#555', 'fontSize': 10}},
        'yAxis': {'type': 'value', 'scale': True, 'splitLine': {'show': True, 'lineStyle': {'color': '#111'}}, 'axisLabel': {'color': '#555', 'fontSize': 10}},
        'series': [{'type': 'line', 'data': state.equity_series, 'showSymbol': False, 'lineStyle': {'color': '#4ade80', 'width': 1}}],
        'backgroundColor': 'transparent',
    }
    ui.echart(opts).classes('w-full h-48 bg-[#0a0a0a] border border-[#222]')

@ui.refreshable
def positions_table():
    cols = [
        {'name': 'ticket', 'label': 'TICKET', 'field': 'ticket', 'align': 'left'},
        {'name': 'symbol', 'label': 'SYM', 'field': 'symbol', 'align': 'left'},
        {'name': 'type_str', 'label': 'DIR', 'field': 'type_str', 'align': 'left'},
        {'name': 'volume', 'label': 'LOT', 'field': 'volume', 'align': 'right'},
        {'name': 'price_open', 'label': 'ENTRY', 'field': 'price_open', 'align': 'right'},
        {'name': 'sl', 'label': 'SL', 'field': 'sl', 'align': 'right'},
        {'name': 'tp', 'label': 'TP', 'field': 'tp', 'align': 'right'},
        {'name': 'profit', 'label': 'PNL', 'field': 'profit', 'align': 'right'},
    ]
    rows = [{**p, 'type_str': 'BUY' if p.get('type') == 0 else 'SELL'} for p in state.open_positions]
    
    ui.table(columns=cols, rows=rows, row_key='ticket').props('dense flat bordered square dark').classes('w-full bg-[#0a0a0a] text-neutral-300 font-mono text-[10px] mt-2')

@ui.refreshable
def signals_feed():
    with ui.column().classes('w-full h-48 bg-[#0a0a0a] border border-[#222] p-2 overflow-y-auto gap-1'):
        ui.label('LIVE SIGNALS').classes('text-[10px] text-neutral-500 uppercase tracking-widest font-sans mb-1')
        for sig in state.recent_signals[:20]:
            color = 'text-green-500' if sig['direction'] == 'bullish' else 'text-red-500'
            dir_short = 'LONG ' if sig['direction'] == 'bullish' else 'SHORT'
            with ui.row().classes('w-full justify-between items-center text-[10px] font-mono border-b border-[#111] pb-1'):
                with ui.row().classes('gap-2 items-center'):
                    ui.label(sig['symbol']).classes('text-neutral-300')
                    ui.label(dir_short).classes(color)
                ui.label(f"[{sig['score']}]").classes('text-neutral-500')

def render():
    stat_cards()
    with ui.row().classes('w-full gap-2 flex-nowrap'):
        with ui.column().classes('flex-grow gap-0'):
            equity_chart()
        with ui.column().classes('w-80 gap-0 shrink-0'):
            signals_feed()
    positions_table()
    ui.timer(2.0, lambda: (stat_cards.refresh(), equity_chart.refresh(),
                           positions_table.refresh(), signals_feed.refresh()))
