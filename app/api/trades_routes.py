from fastapi import APIRouter
from app.binance_client.client import binance_client

router = APIRouter(prefix="/api/trades")

@router.post("/{ticket}/close")
async def close_trade(ticket: int):
    from app.db.session import AsyncSessionLocal
    from app.db.models import Trade
    from sqlalchemy import select
    from app.engine.position_monitor import close_trade_binance
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Trade).where(Trade.id == ticket))
        t = result.scalars().first()
        if not t:
            return {"status": "error", "message": "Trade not found"}
        
        success = await close_trade_binance(t)
        return {"status": "ok" if success else "error"}
