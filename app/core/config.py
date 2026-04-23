from app.db.session import AsyncSessionLocal
from app.db.models import Config
from sqlalchemy import select

async def get_config() -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Config.value).where(Config.key == "main"))
        val = result.scalar()
        return val if val else {}

async def update_config(updates: dict):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Config).where(Config.key == "main"))
        cfg = result.scalar()
        if not cfg:
            cfg = Config(key="main", value=updates, version=1)
            session.add(cfg)
        else:
            cfg.value = {**cfg.value, **updates}
            cfg.version += 1
        await session.commit()
