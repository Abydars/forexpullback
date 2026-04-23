import asyncio
from app.db.session import engine
from app.db.models import Base

async def init_db_async():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def init_db():
    asyncio.run(init_db_async())
