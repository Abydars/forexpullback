from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from app.engine.lifecycle import start_engine, stop_engine
from app.api import (mt5_routes, config_routes, sessions_routes,
                     signals_routes, trades_routes, engine_routes, events_routes)
from app.ws.manager import router as ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_engine()
    yield
    await stop_engine()

app = FastAPI(lifespan=lifespan)
app.mount('/static', StaticFiles(directory='app/static'), name='static')

@app.get('/')
async def index():
    return FileResponse('app/static/index.html')

for r in [mt5_routes.router, config_routes.router, sessions_routes.router,
          signals_routes.router, trades_routes.router, engine_routes.router,
          events_routes.router, ws_router]:
    app.include_router(r)
