from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from contextlib import asynccontextmanager
from app.engine.lifecycle import start_engine, stop_engine
from app.api import (binance_routes, config_routes, sessions_routes,
                     signals_routes, trades_routes, engine_routes, events_routes, auth_routes)
from app.ws.manager import router as ws_router
from app.core.auth import verify_access_token

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_engine()
    yield
    await stop_engine()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    
    # Allow public access to static files and login endpoints
    if path.startswith("/static/") or path == "/login" or path == "/api/auth/login":
        return await call_next(request)
        
    # Check cookie for authentication
    token = request.cookies.get("auth_token")
    if not verify_access_token(token):
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        elif path == "/ws":
            # WebSockets are handled in their own route, but middleware catches upgrade requests
            pass
        else:
            return RedirectResponse(url="/login")
            
    return await call_next(request)

app.mount('/static', StaticFiles(directory='app/static'), name='static')

@app.get('/login')
async def login_page():
    return FileResponse('app/static/login.html')

@app.get('/')
async def index():
    return FileResponse('app/static/index.html')

for r in [auth_routes.router, binance_routes.router, config_routes.router, sessions_routes.router,
          signals_routes.router, trades_routes.router, engine_routes.router,
          events_routes.router, ws_router]:
    app.include_router(r)
