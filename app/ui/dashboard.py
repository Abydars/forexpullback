from nicegui import ui
from app.ui.state import state
from app.core.config import cfg

@ui.refreshable
def render_sidebar():
    from app.ui.mt5_modal import open_mt5_modal
    from app.ui.config_modal import open_config_modal
    from app.engine.lifecycle import start_engine, stop_engine

    # 1. Header
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-2'):
        ui.label('XAUUSD TERMINAL').classes('text-sm font-bold text-white tracking-widest')
        
        acc = state.account or {}
        bal = f"${acc.get('balance', 0):.2f}" if acc else "---"
        status_color = '#3fb950' if state.mt5_connected else '#f85149'
        ui.label(f"MT5: CONNECTED | BAL: {bal}").classes(f'text-[10px] font-bold text-[{status_color}]')
        
        with ui.row().classes('w-full gap-2 flex-nowrap mt-2'):
            ui.button('MT5 LINK', on_click=open_mt5_modal).classes('flex-1 bg-[#21262d] text-[#c9d1d9] text-[10px] h-8 rounded-sm font-bold border border-[#30363d]')
            ui.button('PARAMETERS', on_click=open_config_modal).classes('flex-1 bg-[#21262d] text-[#c9d1d9] text-[10px] h-8 rounded-sm font-bold border border-[#30363d]')
            
        btn_col = 'bg-[#112a1f] text-[#3fb950] border-[#238636]' if state.engine_running else 'bg-[#21262d] text-[#c9d1d9] border-[#30363d]'
        btn_text = 'SYSTEM: ACTIVE' if state.engine_running else 'SYSTEM: INACTIVE'
        
        async def toggle_engine():
            if state.engine_running:
                await stop_engine()
            else:
                await start_engine()
            render_sidebar.refresh()
                
        ui.button(btn_text, on_click=toggle_engine).classes(f'w-full {btn_col} text-xs h-8 rounded-sm font-bold border mt-2')

    # 2. Daily Performance
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-2'):
        ui.label('DAILY PERFORMANCE').classes('text-[9px] text-[#8b949e] tracking-widest uppercase mb-1')
        
        with ui.column().classes('w-full bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
            ui.label('NET RETURN').classes('text-[8px] text-[#8b949e] uppercase mb-1')
            pnl = state.today_pnl
            col = 'text-[#3fb950]' if pnl >= 0 else 'text-[#f85149]'
            ui.label(f"${pnl:+.2f}").classes(f'text-sm font-bold {col}')
            
        with ui.row().classes('w-full gap-2 flex-nowrap'):
            with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
                ui.label('EXECUTIONS').classes('text-[8px] text-[#8b949e] uppercase mb-1')
                ui.label('0').classes('text-xs font-bold text-white')
            with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
                ui.label('WIN/LOSS').classes('text-[8px] text-[#8b949e] uppercase mb-1')
                ui.label('0-0').classes('text-xs font-bold text-[#3fb950]')

    # 3. System Parameters
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-2'):
        ui.label('SYSTEM PARAMETERS').classes('text-[9px] text-[#8b949e] tracking-widest uppercase mb-1')
        with ui.row().classes('w-full gap-2 flex-nowrap'):
            with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
                ui.label('RISK').classes('text-[8px] text-[#8b949e] uppercase mb-1')
                ui.label(f"{cfg.get('risk_percent', 1.0)}%").classes('text-xs font-bold text-[#58a6ff]')
            with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
                ui.label('DD CAP').classes('text-[8px] text-[#8b949e] uppercase mb-1')
                ui.label('2%').classes('text-xs font-bold text-white')
                
        with ui.row().classes('w-full gap-2 flex-nowrap'):
            with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
                ui.label('MAX TRADES').classes('text-[8px] text-[#8b949e] uppercase mb-1')
                ui.label(f"{cfg.get('max_open_positions', 3)}").classes('text-xs font-bold text-white')
            with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
                ui.label('MIN REWARD').classes('text-[8px] text-[#8b949e] uppercase mb-1')
                ui.label(f"{cfg.get('reward_ratio', 2.0)}R").classes('text-xs font-bold text-white')
                
        with ui.column().classes('w-full bg-[#0d1117] border border-[#30363d] p-2 items-center gap-0'):
            ui.label('NEWS RULE').classes('text-[8px] text-[#8b949e] uppercase mb-1')
            ui.label('AVOID').classes('text-xs font-bold text-[#3fb950]')

    ui.timer(5.0, render_sidebar.refresh)

@ui.refreshable
def render_main_panel():
    # 1. Active Exposure
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-0'):
        ui.label('ACTIVE EXPOSURE').classes('text-[9px] text-[#8b949e] tracking-widest uppercase mb-2')
        if not state.open_positions:
            with ui.row().classes('w-full h-12 items-center justify-center bg-[#0d1117] border border-[#30363d]'):
                ui.label('AWAITING MARKET CONDITIONS').classes('text-[9px] text-[#484f58] tracking-widest uppercase')
        else:
            cols = [
                {'name': 'ticket', 'label': 'TICKET', 'field': 'ticket', 'align': 'left'},
                {'name': 'symbol', 'label': 'SYM', 'field': 'symbol', 'align': 'left'},
                {'name': 'volume', 'label': 'LOT', 'field': 'volume', 'align': 'right'},
                {'name': 'price_open', 'label': 'ENTRY', 'field': 'price_open', 'align': 'right'},
                {'name': 'profit', 'label': 'PNL', 'field': 'profit', 'align': 'right'},
            ]
            ui.table(columns=cols, rows=state.open_positions, row_key='ticket').props('dense flat bordered square dark hide-pagination').classes('w-full bg-[#0d1117] text-[#c9d1d9] text-[9px] font-mono')

    # 2. Strategy Flow & Market Context
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-2'):
        ui.label('STRATEGY FLOW & MARKET CONTEXT').classes('text-[9px] text-[#8b949e] tracking-widest uppercase mb-0')
        with ui.row().classes('w-full gap-2'):
            def status_box(title, status, sub=None, col='text-[#3fb950]'):
                with ui.column().classes('flex-1 bg-[#0d1117] border border-[#30363d] p-2 items-center justify-center min-h-[60px] gap-0'):
                    ui.label(title).classes('text-[8px] text-[#8b949e] uppercase mb-1 tracking-widest')
                    ui.label(status).classes(f'text-xs font-bold uppercase {col}')
                    if sub:
                        ui.label(sub).classes('text-[8px] text-[#e3b341] uppercase mt-1')
            
            # Using placeholders as actual engine state is not fully hooked into these visual cues yet
            status_box('H1 TREND BIAS', 'BULLISH', 'PULLBACK-END')
            status_box('M15 FVG ZONE', 'DISCOUNT')
            status_box('SYSTEM FILTERS', 'CLEAR')
            
        with ui.row().classes('w-full gap-2'):
            status_box('M5 LIQUIDITY SWEEP', 'WAITING', col='text-[#c9d1d9]')
            status_box('M5 FVG VALIDATION', 'SCANNING', col='text-[#c9d1d9]')
            status_box('LIVE QUOTE', '---', col='text-[#3fb950]')

    # 3. Rejection Log
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-2 flex-grow overflow-hidden'):
        with ui.row().classes('w-full items-center gap-2 mb-1'):
            ui.icon('do_not_disturb_alt', size='12px').classes('text-[#f85149]')
            ui.label('REJECTION LOG').classes('text-[9px] text-[#8b949e] tracking-widest uppercase')
        
        with ui.element('div').classes('w-full flex-grow overflow-auto bg-[#0d1117] border border-[#30363d] p-2'):
            from app.db.session import SessionLocal
            from app.db.models import SignalRecord
            import json
            
            db = SessionLocal()
            signals = db.query(SignalRecord).filter_by(status='rejected').order_by(SignalRecord.created_at.desc()).limit(30).all()
            if not signals:
                with ui.row().classes('w-full h-full items-center justify-center'):
                    ui.label('LOG EMPTY').classes('text-[9px] text-[#484f58] tracking-widest uppercase')
            else:
                for sig in signals:
                    with ui.row().classes('w-full items-center gap-4 py-1 border-b border-[#21262d] text-[9px]'):
                        ui.label(sig.created_at.strftime('%H:%M:%S')).classes('text-[#8b949e] w-16')
                        ui.label('RR').classes('bg-[#8c4608] text-white px-1 rounded-sm text-[8px]')
                        ui.label(json.dumps(sig.reason)).classes('text-[#c9d1d9] flex-grow truncate')
            db.close()

    # 4. Trade Ledger
    with ui.column().classes('w-full bg-[#161b22] border border-[#30363d] p-3 rounded-sm gap-0 h-[250px]'):
        with ui.row().classes('w-full items-center justify-between mb-2'):
            ui.label('TRADE LEDGER').classes('text-[9px] text-[#8b949e] tracking-widest uppercase')
            ui.label('[VOL: 0 | WIN: 0.0% | NET: $0.00]').classes('text-[9px] text-[#58a6ff] tracking-widest uppercase')
        
        with ui.element('div').classes('w-full h-full overflow-auto bg-[#0d1117] border border-[#30363d]'):
            from app.db.session import SessionLocal
            from app.db.models import TradeRecord
            db = SessionLocal()
            trades = db.query(TradeRecord).filter(TradeRecord.closed_at.isnot(None)).order_by(TradeRecord.opened_at.desc()).limit(20).all()
            if not trades:
                with ui.row().classes('w-full h-full items-center justify-center'):
                    ui.label('LEDGER EMPTY').classes('text-[9px] text-[#484f58] tracking-widest uppercase')
            else:
                # Custom dense table
                with ui.row().classes('w-full justify-between text-[#8b949e] text-[8px] uppercase px-2 py-1 border-b border-[#30363d]'):
                    ui.label('TIMESTAMP').classes('w-24')
                    ui.label('TYPE').classes('w-12')
                    ui.label('ENTRY').classes('w-16 text-right')
                    ui.label('EXIT').classes('w-16 text-right')
                    ui.label('P/L').classes('w-16 text-right')
                
                for t in trades:
                    with ui.row().classes('w-full justify-between text-[#c9d1d9] text-[9px] px-2 py-1 border-b border-[#21262d]'):
                        ui.label(t.closed_at.strftime('%H:%M:%S')).classes('w-24 text-[#8b949e]')
                        col = 'text-[#3fb950]' if t.direction == 'bullish' else 'text-[#f85149]'
                        ui.label('LONG' if t.direction == 'bullish' else 'SHORT').classes(f'w-12 {col}')
                        ui.label(f"{t.entry_price:.5f}").classes('w-16 text-right')
                        ui.label(f"{t.exit_price:.5f}" if t.exit_price else "-").classes('w-16 text-right')
                        p_col = 'text-[#3fb950]' if (t.pnl or 0) >= 0 else 'text-[#f85149]'
                        ui.label(f"{t.pnl:+.2f}" if t.pnl else "0.00").classes(f'w-16 text-right font-bold {p_col}')
            db.close()

    ui.timer(5.0, render_main_panel.refresh)
