import asyncio
from app.engine.scanner import scan_loop
from app.engine.position_monitor import monitor_loop

_tasks = []

async def start_engine():
    global _tasks
    from app.core.state import state
    from app.db.session import AsyncSessionLocal
    from app.db.models import BinanceAccount
    from app.binance_client.client import binance_client
    from app.db.crypto import decrypt_password
    from sqlalchemy import select
    
    # Auto-connect Binance to last saved account
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BinanceAccount).order_by(BinanceAccount.id.desc()).limit(1))
            acc = result.scalar()
            if acc:
                pw_secret = decrypt_password(acc.api_secret_enc)
                key = decrypt_password(acc.api_key_enc)
                await binance_client.connect(key, pw_secret, acc.testnet)
                state.binance_connected = True
                print(f"Auto-connected to Binance")
    except Exception as e:
        print(f"Binance Auto-connect failed: {e}")

    state.engine_running = True
    
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
