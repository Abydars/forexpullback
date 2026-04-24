import asyncio
from app.db.session import engine
from sqlalchemy import text

async def get_current_version(conn) -> int:
    try:
        res = await conn.execute(text("SELECT version FROM schema_version LIMIT 1"))
        row = res.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0

async def set_version(conn, version: int):
    await conn.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)"))
    await conn.execute(text("DELETE FROM schema_version"))
    await conn.execute(text("INSERT INTO schema_version (version) VALUES (:v)"), {"v": version})

async def init_db_async():
    # Keep create_all to create missing tables
    from app.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        current_version = await get_current_version(conn)
        print(f"Current DB Version: {current_version}")
        
        async def v1(c): pass
        
        # Define migrations
        migrations = [
            # v1: Initial setup (handled by create_all)
            v1,
            
            # Add future migrations here, e.g.:
            # async def v2(c): await c.execute(text("ALTER TABLE trades ADD COLUMN new_col TEXT"))
        ]
        
        target_version = len(migrations)
        
        for v in range(current_version, target_version):
            print(f"Applying migration to version {v + 1}...")
            await migrations[v](conn)
            await set_version(conn, v + 1)
            
        if target_version > current_version:
            print(f"Database migrated to version {target_version}")

def init_db():
    asyncio.run(init_db_async())
