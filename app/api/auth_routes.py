from fastapi import APIRouter, Response, Request, HTTPException
from pydantic import BaseModel
from app.core.config import get_config

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    password: str

@router.post("/login")
async def login(req: LoginRequest, response: Response):
    cfg = await get_config()
    expected_password = cfg.get("dashboard_password", "admin")
    
    if req.password == expected_password:
        # Set HttpOnly cookie for 30 days
        response.set_cookie(key="auth_token", value="authenticated", httponly=True, max_age=86400*30)
        return {"status": "ok"}
        
    raise HTTPException(status_code=401, detail="Invalid password")

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("auth_token")
    return {"status": "ok"}
