from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import SignalRecord
import json

@ui.refreshable
def signals_feed():
    db = SessionLocal()
    signals = db.query(SignalRecord).order_by(SignalRecord.created_at.desc()).limit(30).all()
    
    with ui.column().classes('w-full gap-0'):
        for sig in signals:
            color = 'text-green-500' if sig.direction == 'bullish' else 'text-red-500'
            bg_col = 'bg-green-950/10' if sig.direction == 'bullish' else 'bg-red-950/10'
            dir_str = 'LONG ' if sig.direction == 'bullish' else 'SHORT'
            
            with ui.expansion().classes(f'w-full border-b border-[#1a1a1a] text-[10px] font-mono {bg_col}').props('dense expand-icon-class="text-neutral-600"') as exp:
                with exp.add_slot('header'):
                    with ui.row().classes('w-full items-center justify-between py-1'):
                        ui.label(f"{sig.symbol}").classes('font-bold text-neutral-200 w-16')
                        ui.label(dir_str).classes(f'{color} font-bold w-10')
                        ui.label(f"[{sig.score:02.0f}]").classes('text-neutral-400 w-6 text-center')
                        ui.label(sig.status[:4].upper()).classes('text-neutral-500 w-10 text-center')
                        ui.label(sig.created_at.strftime('%H:%M:%S')).classes('text-neutral-600')
                
                with ui.column().classes('p-2 bg-[#000] border-t border-[#1a1a1a] w-full gap-1'):
                    ui.label(f"ENTRY: {sig.entry} | SL: {sig.sl} | TP: {sig.tp}").classes('text-neutral-300 font-bold')
                    ui.label(json.dumps(sig.reason, indent=2)).classes('whitespace-pre text-[9px] text-neutral-500 leading-tight')
                    
    db.close()

def render_signals():
    ui.label('SIGNAL ENGINE').classes('text-[9px] text-neutral-500 bg-[#111] px-2 py-1 border-b border-[#222] w-full tracking-widest')
    with ui.element('div').classes('flex-grow overflow-auto'):
        signals_feed()
    ui.timer(5.0, lambda: signals_feed.refresh())
