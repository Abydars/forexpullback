from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import EventRecord

@ui.refreshable
def logs_table():
    db = SessionLocal()
    events = db.query(EventRecord).order_by(EventRecord.created_at.desc()).limit(100).all()
    rows = []
    for e in events:
        rows.append({
            'time': str(e.created_at),
            'level': e.level,
            'component': e.component,
            'message': e.message
        })
    db.close()
    
    cols = [
        {'name': 'time', 'label': 'Time', 'field': 'time', 'align': 'left'},
        {'name': 'level', 'label': 'Level', 'field': 'level', 'align': 'left'},
        {'name': 'component', 'label': 'Component', 'field': 'component', 'align': 'left'},
        {'name': 'message', 'label': 'Message', 'field': 'message', 'align': 'left'},
    ]
    ui.table(columns=cols, rows=rows, row_key='time').classes('w-full bg-slate-900 mt-4')

def render():
    ui.label('System Logs').classes('text-2xl font-bold mb-4')
    logs_table()
    ui.timer(5.0, lambda: logs_table.refresh())
