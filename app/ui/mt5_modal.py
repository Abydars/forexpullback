from nicegui import ui
from app.mt5_client.client import mt5_client
from app.db.session import SessionLocal
from app.db.models import MT5Account
from app.db.crypto import encrypt, decrypt
from app.ui.state import state

COMMON_EXNESS_SERVERS = [
    'Exness-MT5Real', 'Exness-MT5Real2', 'Exness-MT5Real3', 'Exness-MT5Real5',
    'Exness-MT5Trial', 'Exness-MT5Trial5', 'Exness-MT5Trial9',
]

def load_saved_accounts():
    db = SessionLocal()
    accounts = db.query(MT5Account).all()
    db.close()
    return accounts

def open_mt5_modal():
    with ui.dialog() as dialog, ui.card().classes('w-[500px] bg-slate-900 border border-slate-700'):
        ui.label('Connect to MT5').classes('text-lg font-bold text-slate-200')

        saved = load_saved_accounts()
        if saved:
            ui.label('Saved accounts').classes('text-sm text-slate-400')
            for acc in saved:
                with ui.row().classes('w-full justify-between items-center bg-slate-800 p-2 rounded'):
                    ui.label(f"{acc.login} @ {acc.server}").classes('text-slate-200')
                    ui.button('Reconnect', on_click=lambda a=acc: reconnect(a, dialog)).props('size=sm')
            ui.separator().classes('my-2 border-slate-700')

        server = ui.input('Server').classes('w-full').props('list=servers')
        options_html = "".join(f'<option value="{s}">' for s in COMMON_EXNESS_SERVERS)
        ui.html(f'<datalist id="servers">{options_html}</datalist>')
        login = ui.number('Login', format='%d').classes('w-full')
        password = ui.input('Password', password=True, password_toggle_button=True).classes('w-full')
        path = ui.input('Terminal path (optional)').classes('w-full')

        status_label = ui.label('').classes('text-sm text-slate-400')
        preview = ui.card().classes('hidden w-full bg-slate-800 mt-2')

        async def test_connection():
            status_label.text = 'Connecting...'
            status_label.classes(replace='text-slate-400')
            try:
                info = await mt5_client.connect(server.value, int(login.value),
                                                password.value, path.value or None)
                status_label.text = '✓ Connected'
                status_label.classes(replace='text-emerald-400')
                preview.classes(remove='hidden')
                preview.clear()
                with preview:
                    ui.label(f"Balance: {info['balance']} {info['currency']}").classes('text-slate-200')
                    ui.label(f"Leverage: 1:{info['leverage']}").classes('text-slate-200')
                    ui.label(f"Company: {info['company']}").classes('text-slate-200')
                save_btn.enable()
            except Exception as e:
                status_label.text = f'✗ {e}'
                status_label.classes(replace='text-rose-400')

        def save_and_close(d):
            db = SessionLocal()
            db.query(MT5Account).update({'is_active': False})
            new_acc = MT5Account(
                server=server.value,
                login=int(login.value),
                password_enc=encrypt(password.value),
                path=path.value or None,
                is_active=True
            )
            db.add(new_acc)
            db.commit()
            db.close()
            state.mt5_connected = True
            ui.notify('Connected and saved!')
            d.close()

        with ui.row().classes('w-full justify-between mt-4'):
            ui.button('Test Connection', on_click=test_connection).classes('bg-blue-600')
            save_btn = ui.button('Save & Use', on_click=lambda: save_and_close(dialog)).classes('bg-emerald-600')
            save_btn.disable()
            
    dialog.open()

async def reconnect(acc, dialog):
    try:
        pw = decrypt(acc.password_enc)
        await mt5_client.connect(acc.server, acc.login, pw, acc.path)
        
        db = SessionLocal()
        db.query(MT5Account).update({'is_active': False})
        db.query(MT5Account).filter_by(id=acc.id).update({'is_active': True})
        db.commit()
        db.close()
        
        state.mt5_connected = True
        ui.notify('Reconnected!')
        dialog.close()
    except Exception as e:
        ui.notify(f'Reconnect failed: {e}', color='negative')
