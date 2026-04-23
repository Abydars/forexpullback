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
            'time': e.created_at.strftime('%y-%m-%d %H:%M:%S'),
            'level': e.level,
            'component': e.component,
            'message': e.message
        })
    db.close()
    
    cols = [
        {'name': 'time', 'label': 'TIME', 'field': 'time', 'align': 'left'},
        {'name': 'level', 'label': 'LVL', 'field': 'level', 'align': 'left'},
        {'name': 'component', 'label': 'COMP', 'field': 'component', 'align': 'left'},
        {'name': 'message', 'label': 'MSG', 'field': 'message', 'align': 'left'},
    ]
    ui.table(columns=cols, rows=rows, row_key='time').props('dense flat bordered square dark').classes('w-full bg-[#0a0a0a] text-neutral-300 font-mono text-[10px]')

def render():
    ui.label('SYSTEM_LOGS').classes('text-[10px] text-neutral-500 uppercase tracking-widest font-sans mb-2')
    logs_table()
    ui.timer(5.0, lambda: logs_table.refresh())
