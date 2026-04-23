from fastapi import APIRouter
from app.core.config import get_config, update_config

router = APIRouter(prefix="/api")

@router.get("/config")
async def read_config():
    return await get_config()

@router.patch("/config")
async def patch_config(updates: dict):
    await update_config(updates)
    return {"status": "ok"}
    
@router.post("/symbols/resolve")
async def resolve_symbols(req: dict):
    from app.engine.scanner import symbol_resolver
    await symbol_resolver.refresh()
    generics = req.get("generics", [])
    res = symbol_resolver.resolve_many(generics)
    return {"map": res}
