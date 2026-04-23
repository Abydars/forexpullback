from nicegui import ui
from app.core.config import cfg
from app.db.session import SessionLocal
from app.db.models import SessionRecord
import pytz

IANA_TIMEZONES = pytz.all_timezones

def open_config_modal():
    with ui.dialog() as dialog, ui.card().classes('w-[800px] bg-slate-900 border border-slate-700'):
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('General')
            ui.tab('Symbols')
            ui.tab('Sessions')
            ui.tab('Risk')

        with ui.tab_panels(tabs, value='General').classes('w-full bg-slate-900'):
            with ui.tab_panel('General'):
                max_pos = ui.number('Max Open Positions', value=cfg.get('max_open_positions', 3)).classes('w-full')
                max_per_sym = ui.number('Max Per Symbol', value=cfg.get('max_per_symbol', 1)).classes('w-full')
                max_per_dir = ui.number('Max Per Direction', value=cfg.get('max_per_direction', 2)).classes('w-full')
                sig_thresh = ui.slider(min=0, max=100, value=cfg.get('signal_threshold', 65)).classes('w-full')
                ui.label().bind_text_from(sig_thresh, 'value', lambda v: f"Signal Threshold: {v}")
                scan_int = ui.number('Scan Interval (seconds)', value=cfg.get('scan_interval_seconds', 10)).classes('w-full')
                
            with ui.tab_panel('Symbols'):
                from app.ui.symbol_chip import render_symbols_tab
                render_symbols_tab()

            with ui.tab_panel('Sessions'):
                from app.ui.session_row import render_sessions_tab
                render_sessions_tab()

            with ui.tab_panel('Risk'):
                sl_mode = ui.radio(['structural', 'atr'], value=cfg.get('sl_mode', 'structural')).props('inline')
                atr_mult = ui.number('ATR Multiplier', value=cfg.get('atr_multiplier', 1.5))
                tp_mode = ui.radio(['r_multiple', 'liquidity'], value=cfg.get('tp_mode', 'r_multiple')).props('inline')
                reward_ratio = ui.number('Reward Ratio (R)', value=cfg.get('reward_ratio', 2.0))
                risk_pct = ui.number('Risk Percent (%)', value=cfg.get('risk_percent', 1.0))

        def save_config():
            cfg.set('max_open_positions', max_pos.value)
            cfg.set('max_per_symbol', max_per_sym.value)
            cfg.set('max_per_direction', max_per_dir.value)
            cfg.set('signal_threshold', sig_thresh.value)
            cfg.set('scan_interval_seconds', scan_int.value)
            cfg.set('sl_mode', sl_mode.value)
            cfg.set('atr_multiplier', atr_mult.value)
            cfg.set('tp_mode', tp_mode.value)
            cfg.set('reward_ratio', reward_ratio.value)
            cfg.set('risk_percent', risk_pct.value)
            ui.notify('Config saved!')

        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('Cancel', on_click=dialog.close).classes('bg-slate-700')
            ui.button('Save', on_click=lambda: (save_config(), dialog.close())).classes('bg-blue-600')
            
    dialog.open()
