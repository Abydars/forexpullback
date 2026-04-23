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
    with ui.dialog() as dialog, ui.card().classes('w-[400px] bg-[#0a0a0a] border border-[#222] rounded-none p-4 font-mono text-xs'):
        ui.label('MT5_CONNECTION').classes('text-sm font-bold text-neutral-200 tracking-widest mb-2')

        saved = load_saved_accounts()
        if saved:
            ui.label('SAVED_PROFILES').classes('text-[10px] text-neutral-500 mt-2')
            for acc in saved:
                with ui.row().classes('w-full justify-between items-center bg-[#111] border border-[#222] p-2 mt-1'):
                    ui.label(f"{acc.login} @ {acc.server}").classes('text-neutral-300')
                    ui.button('RECONN', on_click=lambda a=acc: reconnect(a, dialog)).props('outline size=xs color=white')
            ui.element('div').classes('w-full h-px bg-[#222] my-4')

        ui.label('NEW_CONNECTION').classes('text-[10px] text-neutral-500')
        server = ui.input('SERVER').classes('w-full mt-1').props('dense outlined dark list=servers')
        options_html = "".join(f'<option value="{s}">' for s in COMMON_EXNESS_SERVERS)
        ui.html(f'<datalist id="servers">{options_html}</datalist>')
        login = ui.number('LOGIN', format='%d').classes('w-full mt-1').props('dense outlined dark')
        password = ui.input('PASSWORD', password=True, password_toggle_button=True).classes('w-full mt-1').props('dense outlined dark')
        path = ui.input('TERMINAL_PATH').classes('w-full mt-1').props('dense outlined dark')

        status_label = ui.label('').classes('text-[10px] text-neutral-500 mt-2')
        preview = ui.column().classes('hidden w-full bg-[#111] border border-[#222] mt-2 p-2 gap-0 text-[10px]')

        async def test_connection():
            status_label.text = 'CONNECTING...'
            status_label.classes(replace='text-neutral-400')
            try:
                info = await mt5_client.connect(server.value, int(login.value), password.value, path.value or None)
                status_label.text = 'STATUS: CONNECTED'
                status_label.classes(replace='text-green-500 font-bold')
                preview.classes(remove='hidden')
                preview.clear()
                with preview:
                    ui.label(f"BAL: {info['balance']} {info['currency']}").classes('text-neutral-300')
                    ui.label(f"LEV: 1:{info['leverage']}").classes('text-neutral-300')
                    ui.label(f"CMP: {info['company']}").classes('text-neutral-300')
                save_btn.enable()
            except Exception as e:
                status_label.text = f'ERR: {e}'
                status_label.classes(replace='text-red-500')

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
            ui.notify('SAVED', color='black')
            d.close()

        with ui.row().classes('w-full justify-end mt-4 gap-2'):
            ui.button('TEST', on_click=test_connection).props('outline size=sm color=white')
            save_btn = ui.button('SAVE', on_click=lambda: save_and_close(dialog)).props('outline size=sm color=green')
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
        ui.notify('RECONNECTED', color='black')
        dialog.close()
    except Exception as e:
        ui.notify(f'ERR: {e}', color='red')
