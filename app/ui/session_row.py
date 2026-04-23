from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import SessionRecord
from app.ui.config_modal import IANA_TIMEZONES

def load_sessions():
    db = SessionLocal()
    sessions = db.query(SessionRecord).all()
    db.close()
    return sessions

def render_sessions_tab():
    container = ui.column().classes('w-full gap-2')
    
    # Store session UI states so we can save them
    session_rows = []

    def save_sessions():
        db = SessionLocal()
        db.query(SessionRecord).delete()
        for s in session_rows:
            days_mask = sum((1 << i) if cb.value else 0 for i, cb in enumerate(s['days']))
            rec = SessionRecord(
                name=s['name'].value,
                start_time=s['start'].value,
                end_time=s['end'].value,
                tz=s['tz'].value,
                days_mask=days_mask,
                enabled=s['enabled'].value
            )
            db.add(rec)
        db.commit()
        db.close()
        ui.notify('Sessions saved')

    def add_row(session=None):
        row_state = {}
        with container:
            with ui.row().classes('w-full items-center gap-2 p-2 bg-slate-800 rounded') as row_ui:
                row_state['name'] = ui.input('Name', value=session.name if session else '').classes('w-24')
                row_state['start'] = ui.time(value=session.start_time if session else '08:00')
                row_state['end'] = ui.time(value=session.end_time if session else '12:00')
                row_state['tz'] = ui.select(IANA_TIMEZONES, value=session.tz if session else 'UTC', with_input=True).classes('w-48')
                
                days_mask = session.days_mask if session else 0b0011111 # Mon-Fri default
                days_cbs = []
                for i, d in enumerate(['M','T','W','T','F','S','S']):
                    cb = ui.checkbox(d, value=bool(days_mask & (1 << i)))
                    days_cbs.append(cb)
                row_state['days'] = days_cbs
                
                row_state['enabled'] = ui.switch('On', value=session.enabled if session else True)
                
                def delete_row():
                    session_rows.remove(row_state)
                    container.remove(row_ui)
                ui.button(icon='close', on_click=delete_row).props('flat color=red')
                
        session_rows.append(row_state)

    for s in load_sessions():
        add_row(s)
        
    with ui.row().classes('mt-4 gap-2'):
        ui.button('+ Add Session', on_click=lambda: add_row()).classes('bg-slate-700')
        ui.button('Save Sessions', on_click=save_sessions).classes('bg-emerald-600')
