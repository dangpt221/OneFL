import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

# Determine database engine
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Default to SQLite for zero-config local reliability
if "localhost" in db_url and "postgres_secure_password" in db_url:
    db_url = "sqlite+aiosqlite:///./onefl_videotrans.db"

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True if "postgresql" in db_url else False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining async DB sessions in background tasks."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for obtaining async DB sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all database tables."""
    global engine, AsyncSessionLocal
    # Import all models so that Base.metadata knows about them
    from app.models import project, subtitle, speaker, glossary  # noqa
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database initialized successfully on {engine.url.database or 'SQLite'}.")
    except Exception as e:
        logger.warning(f"Database error on {engine.url}: {e}. Auto-switching to SQLite fallback...")
        sqlite_url = "sqlite+aiosqlite:///./onefl_videotrans.db"
        engine = create_async_engine(sqlite_url, echo=False, future=True)
        AsyncSessionLocal.configure(bind=engine)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database initialized successfully.")

    # Safe column migration for SQLite / PostgreSQL
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            migration_cols = [
                ("projects", "dubbed_video_url", "TEXT"),
                ("projects", "dubbed_video_path", "TEXT"),
                ("projects", "dubbed_audio_url", "TEXT"),
                ("projects", "dubbed_audio_path", "TEXT"),
                ("projects", "default_voice", "VARCHAR(50) DEFAULT 'nova'"),
                ("speaker_profiles", "tts_voice", "VARCHAR(50) DEFAULT 'nova'"),
                ("speaker_profiles", "tts_speed", "FLOAT DEFAULT 1.0"),
            ]
            for table, col, col_type in migration_cols:
                try:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};"))
                except Exception:
                    pass  # Column already exists
    except Exception as e:
        logger.debug(f"Migration check: {e}")
