from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import BinanceAccount
from app.binance_client.client import binance_client
from app.db.crypto import encrypt_password
from datetime import datetime

router = APIRouter(prefix="/api/binance", tags=["Binance"])

class BinanceLinkRequest(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool

@router.get("/status")
async def get_status():
    if not binance_client.is_connected():
        return {"connected": False}
    try:
        acc = await binance_client.account_info()
        return {
            "connected": True,
            "testnet": binance_client.testnet,
            "balance": acc.get("totalWalletBalance", "0.0"),
            "equity": acc.get("totalMarginBalance", "0.0")
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}

@router.post("/link")
async def link_binance(req: BinanceLinkRequest):
    try:
        acc_info = await binance_client.connect(req.api_key, req.api_secret, req.testnet)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(BinanceAccount))
            db_acc = result.scalars().first()
            if not db_acc:
                db_acc = BinanceAccount(
                    api_key_enc=encrypt_password(req.api_key),
                    api_secret_enc=encrypt_password(req.api_secret),
                    testnet=req.testnet,
                    is_active=True,
                    last_connected_at=datetime.now()
                )
                db.add(db_acc)
            else:
                db_acc.api_key_enc = encrypt_password(req.api_key)
                db_acc.api_secret_enc = encrypt_password(req.api_secret)
                db_acc.testnet = req.testnet
                db_acc.is_active = True
                db_acc.last_connected_at = datetime.now()
            await db.commit()
            
        return {"success": True, "message": "Binance connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/unlink")
async def unlink_binance():
    await binance_client.disconnect()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BinanceAccount))
        db_acc = result.scalars().first()
        if db_acc:
            db_acc.is_active = False
            await db.commit()
    return {"success": True}
