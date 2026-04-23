from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from mt5_client.client import mt5_client
from mt5_client.symbol_resolver import symbol_resolver
from db.session import get_db
from db.models import MT5Account
from db.crypto import encrypt
from core.logging import log_event

router = APIRouter()

class ConnectRequest(BaseModel):
    server: str
    login: int
    password: str
    path: Optional[str] = None

class ResolveRequest(BaseModel):
    generic: list[str]

@router.post("/connect")
async def connect_mt5(req: ConnectRequest, db=Depends(get_db)):
    try:
        acc = await mt5_client.connect(req.server, req.login, req.password, req.path)
        
        db_acc = db.query(MT5Account).filter(MT5Account.login == req.login).first()
        if not db_acc:
            db_acc = MT5Account(
                server=req.server,
                login=req.login,
                password_enc=encrypt(req.password),
                path=req.path
            )
            db.add(db_acc)
        else:
            db_acc.server = req.server
            db_acc.password_enc = encrypt(req.password)
            db_acc.path = req.path
            
        db.commit()
        
        symbol_resolver.refresh()
        log_event("info", "mt5", f"Connected to {req.server} ({req.login})")
        return {"status": "success", "account": acc.__dict__}
    except Exception as e:
        log_event("error", "mt5", f"Connection failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/disconnect")
async def disconnect_mt5():
    await mt5_client.disconnect()
    log_event("info", "mt5", "Disconnected")
    return {"status": "success"}

@router.get("/account")
def get_account():
    acc = mt5_client.account_info()
    if not acc:
        raise HTTPException(status_code=404, detail="Not connected")
    return acc.__dict__

@router.get("/symbols")
def get_symbols():
    symbols = mt5_client.symbols_get()
    return [{"name": getattr(s, "name", "unknown")} for s in symbols]

@router.post("/symbols/resolve")
def resolve_symbols(req: ResolveRequest):
    result = symbol_resolver.resolve_many(req.generic)
    return result
