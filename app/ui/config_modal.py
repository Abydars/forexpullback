from nicegui import ui
from app.core.config import cfg
from app.db.session import SessionLocal
from app.db.models import SessionRecord
import pytz

def open_config_modal():
    with ui.dialog() as dialog, ui.card().classes('w-[800px] bg-[#0a0a0a] border border-[#30363d] rounded-none p-0 font-mono text-xs'):
        with ui.row().classes('w-full bg-[#161b22] px-4 py-2 border-b border-[#30363d] items-center justify-between'):
            ui.label('SYSTEM_PARAMETERS').classes('text-sm font-bold text-white tracking-widest')
            ui.button(icon='close', on_click=dialog.close).props('flat round size=sm color=white').classes('p-0 m-0')

        with ui.tabs().classes('w-full border-b border-[#30363d] text-[10px] bg-[#0d1117]') as tabs:
            ui.tab('General')
            ui.tab('Symbols')
            ui.tab('Sessions')
            ui.tab('Risk')

        with ui.tab_panels(tabs, value='General').classes('w-full bg-[#0d1117] p-4 text-[#c9d1d9]'):
            with ui.tab_panel('General').classes('p-0 gap-4'):
                max_pos = ui.number('MAX OPEN POSITIONS', value=cfg.get('max_open_positions', 3)).classes('w-full').props('outlined dark dense')
                max_per_sym = ui.number('MAX PER SYMBOL', value=cfg.get('max_per_symbol', 1)).classes('w-full').props('outlined dark dense')
                max_per_dir = ui.number('MAX PER DIRECTION', value=cfg.get('max_per_direction', 2)).classes('w-full').props('outlined dark dense')
                sig_thresh = ui.slider(min=0, max=100, value=cfg.get('signal_threshold', 65)).classes('w-full mt-4')
                ui.label().bind_text_from(sig_thresh, 'value', lambda v: f"SIGNAL THRESHOLD: {v}").classes('text-[10px] text-[#8b949e]')
                scan_int = ui.number('SCAN INTERVAL (SEC)', value=cfg.get('scan_interval_seconds', 10)).classes('w-full').props('outlined dark dense')
                magic_num = ui.number('MAGIC NUMBER', value=cfg.get('magic_number', 123456), format='%d').classes('w-full').props('outlined dark dense')
                
            with ui.tab_panel('Symbols').classes('p-0'):
                from app.ui.symbol_chip import render_symbols_tab
                render_symbols_tab()

            with ui.tab_panel('Sessions').classes('p-0'):
                from app.ui.session_row import render_sessions_tab
                render_sessions_tab()

            with ui.tab_panel('Risk').classes('p-0 gap-4'):
                ui.label('STOP LOSS MODE').classes('text-[10px] text-[#8b949e]')
                sl_mode = ui.radio(['structural', 'atr'], value=cfg.get('sl_mode', 'structural')).props('inline dark dense').classes('text-xs')
                atr_mult = ui.number('ATR MULTIPLIER', value=cfg.get('atr_multiplier', 1.5)).props('outlined dark dense').classes('w-full')
                
                ui.label('TAKE PROFIT MODE').classes('text-[10px] text-[#8b949e] mt-4')
                tp_mode = ui.radio(['r_multiple', 'liquidity'], value=cfg.get('tp_mode', 'r_multiple')).props('inline dark dense').classes('text-xs')
                reward_ratio = ui.number('REWARD RATIO (R)', value=cfg.get('reward_ratio', 2.0)).props('outlined dark dense').classes('w-full')
                risk_pct = ui.number('RISK PERCENT (%)', value=cfg.get('risk_percent', 1.0)).props('outlined dark dense').classes('w-full')

        def save_config():
            cfg.set('max_open_positions', max_pos.value)
            cfg.set('max_per_symbol', max_per_sym.value)
            cfg.set('max_per_direction', max_per_dir.value)
            cfg.set('signal_threshold', sig_thresh.value)
            cfg.set('scan_interval_seconds', scan_int.value)
            cfg.set('magic_number', int(magic_num.value))
            cfg.set('sl_mode', sl_mode.value)
            cfg.set('atr_multiplier', atr_mult.value)
            cfg.set('tp_mode', tp_mode.value)
            cfg.set('reward_ratio', reward_ratio.value)
            cfg.set('risk_percent', risk_pct.value)
            ui.notify('CONFIG SAVED', color='black')

        with ui.row().classes('w-full bg-[#161b22] px-4 py-3 border-t border-[#30363d] justify-end gap-2'):
            ui.button('CANCEL', on_click=dialog.close).props('outline size=sm color=white').classes('text-[10px]')
            ui.button('SAVE', on_click=lambda: (save_config(), dialog.close())).props('outline size=sm color=green').classes('text-[10px]')
            
    dialog.open()
