from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine("sqlite+aiosqlite:///app.db", echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False)
