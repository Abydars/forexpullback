from fastapi import APIRouter
from app.core.config import get_config, update_config

router = APIRouter(prefix="/api")

@router.get("/config")
async def read_config():
    cfg = await get_config()
    # Mask password for UI
    if "dashboard_password" in cfg:
        cfg["dashboard_password"] = ""
    return cfg

@router.patch("/config")
async def patch_config(updates: dict):
    from app.core.auth import hash_password
    
    # Hash password if provided, otherwise remove it from updates to prevent clearing
    if "dashboard_password" in updates:
        pw = updates["dashboard_password"]
        if pw and pw.strip():
            updates["dashboard_password"] = hash_password(pw.strip())
        else:
            del updates["dashboard_password"]
            
    await update_config(updates)
    
    # Force rebuild symbol universe immediately to reflect new settings
    from app.engine.symbol_universe import symbol_universe
    import time
    new_cfg = await get_config()
    new_u = await symbol_universe.build_scan_symbols(new_cfg)
    symbol_universe.cached_universe = new_u
    symbol_universe.last_refresh = time.time()
    
    return {"status": "ok"}
    
@router.post("/symbols/resolve")
async def resolve_symbols(req: dict):
    from app.engine.scanner import symbol_resolver
    await symbol_resolver.refresh()
    generics = req.get("generics", [])
    res = symbol_resolver.resolve_many(generics)
    return {"map": res}
@router.post("/symbols/preview")
async def preview_symbols(cfg: dict):
    from app.engine.symbol_universe import symbol_universe
    # force rebuild
    await symbol_universe.build_scan_symbols(cfg)
    return list(symbol_universe.last_metadata.values()) if hasattr(symbol_universe, 'last_metadata') else []
