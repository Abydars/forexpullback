import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import BinanceAccount
from sqlalchemy import select
from app.binance_client.client import binance_client
from app.db.crypto import decrypt_password

async def test():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(BinanceAccount).where(BinanceAccount.is_active == True))
        acc = res.scalars().first()
            
    await binance_client.connect(decrypt_password(acc.api_key_enc), decrypt_password(acc.api_secret_enc), acc.testnet)
    
    req = {
        'symbol': 'BTCUSDT',
        'side': 'SELL',
        'positionSide': 'LONG',
        'type': 'STOP_MARKET',
        'stopPrice': 90000,
        'closePosition': 'true'
    }
    
    endpoints_to_try = [
        '/fapi/v1/algo/order',
        '/fapi/v1/algoOrder',
        '/sapi/v1/algo/futures/newOrderVp',
        '/fapi/v1/conditionalOrder',
    ]
    
    for ep in endpoints_to_try:
        try:
            res = await binance_client.request('POST', ep, signed=True, params=req)
            print(f"Success with {ep}:", res)
        except Exception as e:
            print(f"Error with {ep}: {e}")

asyncio.run(test())
