import asyncio
from app.engine.scanner import scan_loop
from app.engine.position_monitor import monitor_loop

_tasks = []

async def start_engine():
    global _tasks
    from app.core.state import state
    from app.db.session import AsyncSessionLocal
    from app.db.models import MT5Account
    from app.mt5_client.client import mt5_client
    from app.db.crypto import decrypt_password
    from sqlalchemy import select, text
    
    # Auto-migrate DB
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("ALTER TABLE signals ADD COLUMN result VARCHAR"))
            await db.commit()
    except Exception:
        pass
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("ALTER TABLE signals ADD COLUMN skip_reason VARCHAR"))
            await db.commit()
    except Exception:
        pass
    
    # Auto-connect MT5 to last saved account
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(MT5Account).order_by(MT5Account.id.desc()).limit(1))
            acc = result.scalar()
            if acc:
                pw = decrypt_password(acc.password_enc)
                await mt5_client.connect(acc.server, acc.login, pw, acc.path)
                state.mt5_connected = True
                print(f"Auto-connected to MT5: {acc.login}")
    except Exception as e:
        print(f"MT5 Auto-connect failed: {e}")

    from app.core.config import get_config
    cfg = await get_config()
    state.engine_running = cfg.get("engine_running", False)
    
    from datetime import datetime
    import pytz
    from app.db.models import Event
    msg = f"Engine restored as {'STARTED' if state.engine_running else 'STOPPED'} after restart"
    print(msg)
    try:
        async with AsyncSessionLocal() as db:
            ev = Event(level="INFO", component="system", message=msg)
            db.add(ev)
            await db.commit()
    except Exception:
        pass
    
    _tasks = [
        asyncio.create_task(scan_loop()),
        asyncio.create_task(monitor_loop())
    ]

async def stop_engine():
    global _tasks
    for t in _tasks:
        t.cancel()
        
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
        _tasks.clear()
