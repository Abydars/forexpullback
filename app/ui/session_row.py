from nicegui import ui
from app.db.session import SessionLocal
from app.db.models import SessionRecord
import pytz

def load_sessions():
    db = SessionLocal()
    sessions = db.query(SessionRecord).all()
    db.close()
    return sessions

def render_sessions_tab():
    container = ui.column().classes('w-full gap-2')
    
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
        ui.notify('SESSIONS SAVED', color='black')

    def add_row(session=None):
        row_state = {}
        with container:
            with ui.row().classes('w-full items-center justify-between gap-2 p-2 bg-[#161b22] border border-[#30363d]') as row_ui:
                row_state['name'] = ui.input('NAME', value=session.name if session else '').classes('w-20 text-xs').props('dense outlined dark')
                row_state['start'] = ui.time(value=session.start_time if session else '08:00').classes('w-24 text-xs').props('dense outlined dark mask="time" format24h')
                row_state['end'] = ui.time(value=session.end_time if session else '12:00').classes('w-24 text-xs').props('dense outlined dark mask="time" format24h')
                row_state['tz'] = ui.select(pytz.all_timezones, value=session.tz if session else 'UTC', with_input=True).classes('w-40 text-xs').props('dense outlined dark')
                
                days_mask = session.days_mask if session else 0b0011111 # Mon-Fri default
                days_cbs = []
                with ui.row().classes('gap-1'):
                    for i, d in enumerate(['M','T','W','T','F','S','S']):
                        cb = ui.checkbox(d, value=bool(days_mask & (1 << i))).props('dark dense size=xs').classes('text-[10px]')
                        days_cbs.append(cb)
                row_state['days'] = days_cbs
                
                row_state['enabled'] = ui.switch('ON', value=session.enabled if session else True).props('dark dense size=xs').classes('text-[10px]')
                
                def delete_row():
                    session_rows.remove(row_state)
                    container.remove(row_ui)
                ui.button(icon='close', on_click=delete_row).props('flat size=sm round color=red')
                
        session_rows.append(row_state)

    for s in load_sessions():
        add_row(s)
        
    with ui.row().classes('mt-4 gap-2'):
        ui.button('+ ADD SESSION', on_click=lambda: add_row()).props('outline size=sm color=white')
        ui.button('SAVE SESSIONS', on_click=save_sessions).props('outline size=sm color=green')
