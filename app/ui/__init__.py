from nicegui import ui
from app.ui.state import state
import asyncio

def build_status_strip():
    with ui.row().classes('items-center gap-4'):
        ui.label().bind_text_from(state, 'active_sessions', lambda s: f"{len(s)} Active Sessions").classes('text-sm px-2 py-1 bg-slate-800 rounded text-slate-300')
        ui.label().bind_text_from(state, 'open_positions', lambda p: f"{len(p)} Positions").classes('text-sm px-2 py-1 bg-slate-800 rounded text-slate-300')
        ui.label().bind_text_from(state, 'today_pnl', lambda p: f"PnL: {p:.2f}").classes('text-sm px-2 py-1 bg-slate-800 rounded font-mono text-slate-300')

def build_action_buttons():
    from app.ui.mt5_modal import open_mt5_modal
    from app.ui.config_modal import open_config_modal
    from app.engine.lifecycle import start_engine, stop_engine

    with ui.row().classes('items-center gap-2'):
        # MT5 Dot
        mt5_dot = ui.icon('circle', size='xs').classes('text-red-500')
        ui.timer(2.0, lambda: mt5_dot.classes(replace='text-green-500' if state.mt5_connected else 'text-red-500'))
        
        ui.button('Connect', on_click=open_mt5_modal).props('size=sm').classes('bg-slate-700')
        ui.button('Settings', on_click=open_config_modal, icon='settings').props('size=sm').classes('bg-slate-700')
        
        async def toggle_engine():
            if state.engine_running:
                await stop_engine()
                btn.text = 'Start Engine'
                btn.props('color=green')
            else:
                await start_engine()
                btn.text = 'Stop Engine'
                btn.props('color=red')
                
        btn = ui.button('Stop Engine' if state.engine_running else 'Start Engine', 
                        on_click=toggle_engine,
                        color='red' if state.engine_running else 'green').props('size=sm')

def build_layout():
    with ui.header().classes('items-center justify-between bg-slate-900 p-4 border-b border-slate-800'):
        ui.label('Forex Pullback Bot').classes('text-xl font-bold text-blue-400')
        build_status_strip()
        build_action_buttons()

    with ui.tabs().classes('w-full border-b border-slate-800') as tabs:
        ui.tab('Dashboard')
        ui.tab('Trades')
        ui.tab('Signals')
        ui.tab('Logs')

    with ui.tab_panels(tabs, value='Dashboard').classes('w-full bg-slate-950 text-slate-200'):
        with ui.tab_panel('Dashboard'):
            from app.ui.dashboard import render as render_dashboard
            render_dashboard()
        with ui.tab_panel('Trades'):
            from app.ui.trades import render as render_trades
            render_trades()
        with ui.tab_panel('Signals'):
            from app.ui.signals import render as render_signals
            render_signals()
        with ui.tab_panel('Logs'):
            from app.ui.logs import render as render_logs
            render_logs()
