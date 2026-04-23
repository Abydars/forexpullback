from nicegui import ui
from app.ui.state import state
import asyncio

def build_status_strip():
    with ui.row().classes('items-center gap-2 text-xs font-mono'):
        ui.label().bind_text_from(state, 'active_sessions', lambda s: f"SESS: {len(s)}").classes('px-1.5 py-0.5 bg-[#111] border border-[#222] text-neutral-400')
        ui.label().bind_text_from(state, 'open_positions', lambda p: f"POS: {len(p)}").classes('px-1.5 py-0.5 bg-[#111] border border-[#222] text-neutral-400')
        ui.label().bind_text_from(state, 'today_pnl', lambda p: f"PNL: {p:+.2f}").classes('px-1.5 py-0.5 bg-[#111] border border-[#222] text-neutral-200')

def build_action_buttons():
    from app.ui.mt5_modal import open_mt5_modal
    from app.ui.config_modal import open_config_modal
    from app.engine.lifecycle import start_engine, stop_engine

    with ui.row().classes('items-center gap-2'):
        mt5_dot = ui.icon('circle', size='10px').classes('text-red-500')
        ui.timer(2.0, lambda: mt5_dot.classes(replace='text-green-500' if state.mt5_connected else 'text-red-500'))
        
        ui.button('CNCT', on_click=open_mt5_modal).props('outline size=sm color=white').classes('text-[10px] font-mono font-bold')
        ui.button('CFG', on_click=open_config_modal).props('outline size=sm color=white').classes('text-[10px] font-mono font-bold')
        
        async def toggle_engine():
            if state.engine_running:
                await stop_engine()
                btn.text = 'START'
                btn.props('outline color=white')
            else:
                await start_engine()
                btn.text = 'STOP'
                btn.props('outline color=red')
                
        btn = ui.button('STOP' if state.engine_running else 'START', 
                        on_click=toggle_engine).props('outline size=sm color=' + ('red' if state.engine_running else 'white')).classes('text-[10px] font-mono font-bold')

def build_layout():
    ui.query('body').classes('bg-[#000]')
    
    with ui.header().classes('items-center justify-between bg-[#0a0a0a] px-4 py-2 border-b border-[#222]'):
        ui.label('PULLBACK_TERM').classes('text-sm font-mono font-bold text-neutral-200 tracking-wider')
        build_status_strip()
        build_action_buttons()

    with ui.tabs().classes('w-full border-b border-[#222] text-xs font-mono') as tabs:
        ui.tab('DASH', label='DASH')
        ui.tab('TRADES', label='TRADES')
        ui.tab('SIG', label='SIG')
        ui.tab('LOGS', label='LOGS')

    with ui.tab_panels(tabs, value='DASH').classes('w-full bg-[#000] text-neutral-200 p-0'):
        with ui.tab_panel('DASH').classes('p-4'):
            from app.ui.dashboard import render as render_dashboard
            render_dashboard()
        with ui.tab_panel('TRADES').classes('p-4'):
            from app.ui.trades import render as render_trades
            render_trades()
        with ui.tab_panel('SIG').classes('p-4'):
            from app.ui.signals import render as render_signals
            render_signals()
        with ui.tab_panel('LOGS').classes('p-4'):
            from app.ui.logs import render as render_logs
            render_logs()
