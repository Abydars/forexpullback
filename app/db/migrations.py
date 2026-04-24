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
        
        async def v2(c):
            # SQLite ALTER TABLE for adding columns
            try: await c.execute(text("ALTER TABLE trades ADD COLUMN parent_trade_id INTEGER"))
            except Exception: pass
            try: await c.execute(text("ALTER TABLE trades ADD COLUMN dca_index INTEGER DEFAULT 0"))
            except Exception: pass
            try: await c.execute(text("ALTER TABLE trades ADD COLUMN group_id VARCHAR"))
            except Exception: pass

        async def v3(c):
            columns_to_add = [
                ("exchange", "VARCHAR DEFAULT 'binance'"),
                ("order_id", "VARCHAR"),
                ("client_order_id", "VARCHAR"),
                ("position_side", "VARCHAR DEFAULT 'LONG'"),
                ("sl_order_id", "VARCHAR"),
                ("tp_order_id", "VARCHAR"),
                ("commission", "FLOAT DEFAULT 0.0")
            ]
            for col_name, col_type in columns_to_add:
                try: await c.execute(text(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}"))
                except Exception: pass

        # Define migrations
        migrations = [
            # v1: Initial setup (handled by create_all)
            v1,
            v2,
            v3
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
