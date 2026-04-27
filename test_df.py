import asyncio
from app.binance_client.client import binance_client
async def main():
    await binance_client.connect("a", "b", True)
    df = await binance_client.get_rates("BTCUSDT", "M5", 5)
    print(df.columns)
    print(df.iloc[-1])
asyncio.run(main())
