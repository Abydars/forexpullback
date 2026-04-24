from fastapi import APIRouter
from app.binance_client.client import binance_client

router = APIRouter(prefix="/api/trades")

@router.post("/{ticket}/close")
async def close_trade(ticket: str):
    from app.db.session import AsyncSessionLocal
    from app.db.models import Trade
    from sqlalchemy import select
    from app.engine.position_monitor import close_trade_binance
    
    if ticket.startswith('ext_'):
        # External trade ticket format: ext_SYMBOL_SIDE
        parts = ticket.split('_')
        if len(parts) >= 3:
            sym = parts[1]
            side = parts[2] # LONG or SHORT
            
            # Fetch position to know the exact remaining quantity
            positions = await binance_client.get_positions()
            p = next((x for x in positions if x['symbol'] == sym and x['positionSide'] == side), None)
            if not p:
                return {"status": "error", "message": "Position not found on Binance"}
                
            qty = abs(float(p['positionAmt']))
            if qty <= 0:
                return {"status": "error", "message": "Position already closed"}
                
            # Close the entire remaining position directly
            req = {
                'symbol': sym,
                'side': 'SELL' if side == 'LONG' else 'BUY',
                'positionSide': side,
                'type': 'MARKET',
                'quantity': qty,
            }
            try:
                await binance_client.order_send(req)
                return {"status": "ok"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # Normal DB tracked trade
    try:
        ticket_id = int(ticket)
    except ValueError:
        return {"status": "error", "message": "Invalid ticket ID"}
        
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Trade).where(Trade.id == ticket_id))
        t = result.scalars().first()
        if not t:
            return {"status": "error", "message": "Trade not found"}
        
        success = await close_trade_binance(t)
        return {"status": "ok" if success else "error"}
