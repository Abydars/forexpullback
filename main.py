from nicegui import ui, app
from app.db.migrations import init_db
from app.engine.lifecycle import start_engine, stop_engine
from app.ui import build_layout

init_db()
build_layout()
app.on_startup(start_engine)
app.on_shutdown(stop_engine)
ui.run(title='Forex Pullback Bot', port=8080, reload=False, show=False, dark=True)
