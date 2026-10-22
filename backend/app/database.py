import logging
import asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
from app.config import settings

logger = logging.getLogger(__name__)

# Determine database engine
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

if db_url.startswith('sqlite+aiosqlite:///./'):
    from pathlib import Path
    location = (settings.ROOT_DIR / 'backend' / db_url.split('///./', 1)[1]).resolve()
    db_url = 'sqlite+aiosqlite:///' + location.as_posix()
is_postgres = "postgresql" in db_url
engine_kwargs = {
    "echo": False,
    "future": True,
}

if is_postgres:
    engine_kwargs.update({
        "pool_size": getattr(settings, "DB_POOL_SIZE", 20),
        "max_overflow": getattr(settings, "DB_MAX_OVERFLOW", 10),
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    })

engine = create_async_engine(db_url, **engine_kwargs)
if not is_postgres:
    @event.listens_for(engine.sync_engine, 'connect')
    def sqlite_pragmas(connection, _record):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=30000')
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def _close_session(session: AsyncSession) -> None:
    """Finish rollback/connection return even when the caller disconnects."""
    cleanup = asyncio.create_task(session.close())
    cancelled = False
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            if cleanup.cancelled():
                raise
            cancelled = True
    try:
        cleanup.result()
    except Exception:
        logger.exception('Database session cleanup failed')
        raise
    if cancelled:
        raise asyncio.CancelledError()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining async DB sessions in background tasks."""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        # AsyncSession.close rolls back an unfinished transaction and releases
        # its connection. Shield the entire operation, not competing close calls.
        await _close_session(session)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for obtaining async DB sessions."""
    async with get_async_session() as session:
        yield session


async def init_db():
    """Use one database; an unavailable production DB is a startup error."""
    from app.services.db_migrator import run_migrations
    await run_migrations(engine)
    logger.info('Database initialized and migrated (%s)', engine.dialect.name)
