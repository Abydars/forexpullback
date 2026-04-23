from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import SignalRecord
import json

@ui.refreshable
def signals_feed():
    db = SessionLocal()
    signals = db.query(SignalRecord).order_by(SignalRecord.created_at.desc()).limit(50).all()
    
    with ui.column().classes('w-full gap-1'):
        for sig in signals:
            with ui.expansion().classes('w-full bg-[#0a0a0a] border border-[#222] font-mono text-xs').props('dense expand-icon-class="text-neutral-500"') as exp:
                with exp.add_slot('header'):
                    with ui.row().classes('w-full items-center justify-between'):
                        color = 'text-green-500' if sig.direction == 'bullish' else 'text-red-500'
                        dir_str = 'LONG ' if sig.direction == 'bullish' else 'SHORT'
                        ui.label(f"{sig.symbol}").classes('font-bold text-neutral-200 w-20')
                        ui.label(dir_str).classes(f'{color} w-16')
                        ui.label(f"SCR:{sig.score:02.0f}").classes('text-neutral-400 w-16')
                        ui.label(f"STS:{sig.status.upper()}").classes('text-neutral-500 w-24')
                        ui.label(sig.created_at.strftime('%H:%M:%S')).classes('text-neutral-500')
                
                with ui.column().classes('p-2 bg-[#050505] border-t border-[#111]'):
                    ui.label(json.dumps(sig.reason, indent=2)).classes('whitespace-pre text-[10px] text-neutral-400')
                    
    db.close()

def render():
    ui.label('SIGNAL_LOG').classes('text-[10px] text-neutral-500 uppercase tracking-widest font-sans mb-2')
    signals_feed()
    ui.timer(5.0, lambda: signals_feed.refresh())
