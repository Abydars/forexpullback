import asyncio
import json
from app.db.session import AsyncSessionLocal
from app.db.models import Config
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Config).where(Config.key == "main"))
        cfg = result.scalar()
        print("BEFORE:", json.dumps(cfg.value if cfg else {}))

asyncio.run(main())
