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
            'time': e.created_at.strftime('%H:%M:%S'),
            'level': e.level,
            'msg': e.message
        })
    db.close()
    
    with ui.column().classes('w-full gap-0 text-[9px] font-mono'):
        for r in rows:
            col = 'text-red-400' if r['level'] in ['ERROR', 'CRITICAL'] else ('text-yellow-400' if r['level'] == 'WARNING' else 'text-neutral-500')
            with ui.row().classes('w-full gap-2 px-2 py-0.5 border-b border-[#111]'):
                ui.label(r['time']).classes('text-neutral-600')
                ui.label(r['level'][:4]).classes(col)
                ui.label(r['msg']).classes('text-neutral-400 truncate flex-grow')

def render_logs():
    with ui.element('div').classes('flex-grow overflow-auto bg-transparent'):
        logs_table()
    ui.timer(5.0, lambda: logs_table.refresh())
