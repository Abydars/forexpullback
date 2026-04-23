from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import SignalRecord
import json

@ui.refreshable
def signals_feed():
    db = SessionLocal()
    signals = db.query(SignalRecord).order_by(SignalRecord.created_at.desc()).limit(50).all()
    
    with ui.column().classes('w-full gap-4'):
        for sig in signals:
            with ui.card().classes('w-full bg-slate-900 border border-slate-800'):
                with ui.row().classes('justify-between w-full items-center'):
                    with ui.row().classes('items-center gap-2'):
                        color = 'text-green-400' if sig.direction == 'bullish' else 'text-red-400'
                        ui.label(sig.symbol).classes(f'text-lg font-bold {color}')
                        ui.label(f"Score: {sig.score}").classes('bg-slate-800 px-2 rounded text-sm')
                        ui.label(f"Status: {sig.status}").classes('text-sm text-slate-400')
                    ui.label(str(sig.created_at)).classes('text-sm text-slate-500')
                
                with ui.expansion('Reasoning', icon='info').classes('w-full mt-2'):
                    ui.label(json.dumps(sig.reason, indent=2)).classes('font-mono whitespace-pre text-sm text-slate-400')
                    
    db.close()

def render():
    ui.label('Signals Feed').classes('text-2xl font-bold mb-4')
    signals_feed()
    ui.timer(5.0, lambda: signals_feed.refresh())
