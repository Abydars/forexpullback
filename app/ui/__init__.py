from nicegui import ui
from app.ui.state import state
import asyncio

def build_header():
    from app.ui.mt5_modal import open_mt5_modal
    from app.ui.config_modal import open_config_modal
    from app.engine.lifecycle import start_engine, stop_engine

    with ui.row().classes('w-full items-center justify-between bg-[#111] border border-[#222] px-3 py-1'):
        with ui.row().classes('items-center gap-4'):
            ui.label('FX_PULLBACK_TERM').classes('text-xs font-bold text-neutral-200 tracking-widest')
            
            with ui.row().classes('gap-3 text-[10px] items-center border-l border-[#333] pl-4'):
                ui.label().bind_text_from(state, 'active_sessions', lambda s: f"SESS: {len(s)}").classes('text-neutral-400')
                ui.label().bind_text_from(state, 'open_positions', lambda p: f"POS: {len(p)}").classes('text-neutral-400')
                ui.label().bind_text_from(state, 'today_pnl', lambda p: f"PNL: {p:+.2f}").classes('text-neutral-200')
                
        with ui.row().classes('items-center gap-2'):
            mt5_dot = ui.icon('circle', size='8px').classes('text-red-500')
            ui.timer(2.0, lambda: mt5_dot.classes(replace='text-green-500' if state.mt5_connected else 'text-red-500'))
            
            ui.button('CNCT', on_click=open_mt5_modal).props('outline size=xs color=white').classes('text-[10px]')
            ui.button('CFG', on_click=open_config_modal).props('outline size=xs color=white').classes('text-[10px]')
            
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
                            on_click=toggle_engine).props('outline size=xs color=' + ('red' if state.engine_running else 'white')).classes('text-[10px]')

def build_layout():
    # Force the body to be unscrollable and fully dark
    ui.add_head_html('<style>body { margin: 0; padding: 0; overflow: hidden; background-color: #050505; color: #d4d4d4; font-family: monospace; }</style>')
    
    with ui.column().classes('w-full h-screen p-2 gap-2'):
        build_header()
        
        # Single screen 4-pane grid layout
        with ui.element('div').classes('grid grid-cols-12 grid-rows-2 gap-2 w-full h-[calc(100vh-3.5rem)]'):
            
            # TOP LEFT: Chart & Account Stats
            with ui.element('div').classes('col-span-8 row-span-1 bg-[#0a0a0a] border border-[#222] flex flex-col relative'):
                from app.ui.dashboard import render_chart
                render_chart()
                
            # BOTTOM LEFT: Open Positions
            with ui.element('div').classes('col-span-8 row-span-1 bg-[#0a0a0a] border border-[#222] flex flex-col overflow-hidden'):
                from app.ui.dashboard import render_positions
                render_positions()
                
            # TOP RIGHT: Signals
            with ui.element('div').classes('col-span-4 row-span-1 bg-[#0a0a0a] border border-[#222] flex flex-col overflow-hidden'):
                from app.ui.signals import render_signals
                render_signals()
                
            # BOTTOM RIGHT: Trades / Logs
            with ui.element('div').classes('col-span-4 row-span-1 bg-[#0a0a0a] border border-[#222] flex flex-col overflow-hidden'):
                with ui.tabs().classes('w-full h-8 min-h-[2rem] bg-[#111] text-[10px] m-0 p-0 border-b border-[#222]') as right_tabs:
                    ui.tab('TRADES', label='EXECUTION HISTORY').classes('m-0 p-2 min-h-0 text-[9px] tracking-widest text-neutral-400')
                    ui.tab('LOGS', label='SYSTEM LOGS').classes('m-0 p-2 min-h-0 text-[9px] tracking-widest text-neutral-400')
                
                with ui.tab_panels(right_tabs, value='TRADES').classes('flex-grow p-0 bg-transparent h-[calc(100%-2rem)]'):
                    with ui.tab_panel('TRADES').classes('p-0 h-full flex flex-col overflow-hidden'):
                        from app.ui.trades import render_trades
                        render_trades()
                    with ui.tab_panel('LOGS').classes('p-0 h-full flex flex-col overflow-hidden'):
                        from app.ui.logs import render_logs
                        render_logs()
