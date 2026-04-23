import asyncio
import logging
from backend.mt5_client.client import mt5_client
from backend.core.state import engine_state

async def reconnect_loop():
    backoff = 1
    max_backoff = 60
    
    while True:
        if not mt5_client.is_connected() and engine_state.is_running:
            logging.info(f"Attempting to reconnect in {backoff} seconds...")
            await asyncio.sleep(backoff)
            
            try:
                # get account info from db
                # this is pseudo-code for now, will implement properly
                # if success:
                #    backoff = 1
                # else:
                #    backoff = min(max_backoff, backoff * 2)
                pass
            except Exception as e:
                logging.error(f"Reconnect failed: {e}")
                backoff = min(max_backoff, backoff * 2)
        else:
            await asyncio.sleep(5)
