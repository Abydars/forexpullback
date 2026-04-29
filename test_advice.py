import asyncio
import sys
from app.db.session import AsyncSessionLocal
from app.db.models import Trade
from app.engine.position_monitor import evaluate_exit_advice
from app.mt5_client.client import mt5_client
from sqlalchemy import select

async def main():
    await mt5_client.connect()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Trade).where(Trade.closed_at == None))
        open_trades = result.scalars().all()
        positions = await mt5_client.get_positions()
        pos_dict = {p['ticket']: p for p in positions}
        for t in open_trades:
            if t.ticket in pos_dict:
                p = pos_dict[t.ticket]
                try:
                    advice = await evaluate_exit_advice(p, t, t.symbol)
                    print(f"Ticket {t.ticket}: {advice}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
