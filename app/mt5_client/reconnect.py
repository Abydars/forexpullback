import asyncio
import logging
from app.mt5_client.client import mt5_client
from app.db.session import SessionLocal
from app.db.models import MT5Account
from app.db.crypto import decrypt

logger = logging.getLogger("reconnect")

async def auto_reconnect_loop():
    backoff = 1
    max_backoff = 60
    
    while True:
        await asyncio.sleep(backoff)
        if not mt5_client.is_connected():
            db = SessionLocal()
            active_account = db.query(MT5Account).filter_by(is_active=True).first()
            if active_account:
                try:
                    logger.info(f"Attempting to reconnect to MT5 {active_account.login}...")
                    password = decrypt(active_account.password_enc)
                    await mt5_client.connect(
                        server=active_account.server,
                        login=active_account.login,
                        password=password,
                        path=active_account.path
                    )
                    logger.info("Reconnected successfully.")
                    backoff = 1 # reset backoff
                except Exception as e:
                    logger.error(f"Reconnect failed: {e}")
                    backoff = min(backoff * 2, max_backoff)
            db.close()
