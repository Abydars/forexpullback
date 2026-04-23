from fastapi import APIRouter
from app.mt5_client.client import mt5_client

router = APIRouter(prefix="/api/trades")

@router.post("/{ticket}/close")
async def close_trade(ticket: int):
    res = await mt5_client.position_close(ticket)
    return {"status": "ok", "result": res}
