from fastapi import APIRouter, Response, Request, HTTPException
from pydantic import BaseModel
from app.core.config import get_config
from app.core.auth import verify_password, hash_password, create_access_token
import os

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    password: str

@router.post("/login")
async def login(req_body: LoginRequest, req: Request, response: Response):
    cfg = await get_config()
    
    # Environment variable has top priority, then DB config, then default "admin"
    env_password = os.environ.get("DASHBOARD_PASSWORD")
    if env_password:
        expected_hashed = hash_password(env_password)
    else:
        # Default is admin
        expected_hashed = cfg.get("dashboard_password", hash_password("admin"))
        
        # Backward compatibility for plain-text passwords stored before the hashing update
        if len(expected_hashed) != 64:
            expected_hashed = hash_password(expected_hashed)
    
    if verify_password(req_body.password, expected_hashed):
        token = create_access_token()
        # Set HttpOnly, dynamic Secure, Lax SameSite cookie
        is_secure = req.url.scheme == "https" or req.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(
            key="auth_token", 
            value=token, 
            httponly=True, 
            secure=is_secure, 
            samesite="lax", 
            max_age=86400*30
        )
        return {"status": "ok"}
        
    raise HTTPException(status_code=401, detail="Invalid password")

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("auth_token")
    return {"status": "ok"}
