from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.mt5_client.client import mt5_client
from app.db.session import AsyncSessionLocal
from app.db.models import MT5Account
from sqlalchemy import select

router = APIRouter(prefix="/api/mt5")

class ConnectRequest(BaseModel):
    server: str
    login: int
    password: str
    path: Optional[str] = None

@router.post("/connect")
async def connect_mt5(req: ConnectRequest):
    acc = await mt5_client.connect(req.server, req.login, req.password, req.path)
    
    from app.db.crypto import encrypt_password
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MT5Account).where(MT5Account.login == req.login, MT5Account.server == req.server))
        existing = result.scalar()
        if not existing:
            existing = MT5Account(server=req.server, login=req.login, password_enc=encrypt_password(req.password), path=req.path)
            db.add(existing)
        else:
            existing.password_enc = encrypt_password(req.password)
            existing.path = req.path
        await db.commit()
    
    from app.core.state import state
    from app.ws.manager import broadcast
    state.mt5_connected = True
    await broadcast({"type": "mt5.connection", "state": "connected"})
    
    return acc

@router.get("/accounts")
async def get_accounts():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MT5Account))
        return [{"server": a.server, "login": a.login, "path": a.path} for a in result.scalars().all()]
