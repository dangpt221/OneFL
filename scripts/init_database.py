"""OneFL Database Provisioning & Migration Utility.

Initializes PostgreSQL 16 database and tables for OneFL.
Falls back safely to local SQLite when PostgreSQL is offline.
"""

import sys
import asyncio
import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, inspect

# Add backend directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.config import settings
from app.database import Base
from app.models import Project, VideoChunk, SubtitleCue, SpeakerProfile, RelationshipMatrix, GlossaryTerm  # noqa

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("onefl-db-init")


async def try_create_postgres_database(user, password, host, port, db_name):
    """Attempts to connect to PostgreSQL default db and create the target database if missing."""
    try:
        import asyncpg
        logger.info(f"Checking PostgreSQL instance at {host}:{port} for database '{db_name}'...")
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database="postgres",
            timeout=3.0
        )
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            logger.info(f"Database '{db_name}' does not exist. Creating...")
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Database '{db_name}' created successfully!")
        else:
            logger.info(f"Database '{db_name}' already exists.")
        await conn.close()
        return True
    except Exception as e:
        logger.warning(f"Could not connect to PostgreSQL server: {e}")
        return False


async def init_database():
    """Initializes tables on PostgreSQL or fallback SQLite."""
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    pg_ready = False
    if "postgresql" in db_url:
        pg_ready = await try_create_postgres_database(
            user=settings.POSTGRES_USER or "postgres",
            password=settings.POSTGRES_PASSWORD or "postgres",
            host=settings.POSTGRES_HOST or "localhost",
            port=settings.POSTGRES_PORT or 5432,
            db_name=settings.POSTGRES_DB or "onefl_videotrans"
        )

    target_url = db_url if pg_ready else "sqlite+aiosqlite:///./onefl_videotrans.db"
    db_type = "PostgreSQL (asyncpg)" if pg_ready else "SQLite (aiosqlite fallback)"
    logger.info(f"Connecting to {db_type} -> {target_url}...")

    engine_kwargs = {"echo": False, "future": True}
    if "postgresql" in target_url:
        engine_kwargs.update({
            "pool_size": 10,
            "max_overflow": 5,
            "pool_pre_ping": True,
            "pool_recycle": 3600
        })

    engine = create_async_engine(target_url, **engine_kwargs)

    try:
        async with engine.begin() as conn:
            logger.info("Creating all OneFL schema tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All tables created successfully.")

            # Apply migrations for new columns
            migration_cols = [
                ("projects", "dubbed_video_url", "TEXT"),
                ("projects", "dubbed_video_path", "TEXT"),
                ("projects", "dubbed_audio_url", "TEXT"),
                ("projects", "dubbed_audio_path", "TEXT"),
                ("projects", "default_voice", "VARCHAR(50) DEFAULT 'vi-VN-HoaiMyNeural'"),
                ("speaker_profiles", "tts_voice", "VARCHAR(50) DEFAULT 'vi-VN-HoaiMyNeural'"),
                ("speaker_profiles", "tts_speed", "FLOAT DEFAULT 1.0"),
            ]
            for table, col, col_type in migration_cols:
                try:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};"))
                except Exception:
                    pass  # Column already exists

        # Verify created tables
        async with engine.connect() as conn:
            def get_tables_info(sync_conn):
                inspector = inspect(sync_conn)
                return {table: len(inspector.get_columns(table)) for table in inspector.get_table_names()}

            tables = await conn.run_sync(get_tables_info)
            logger.info("=" * 60)
            logger.info(f"DATABASE PROVISIONING COMPLETE ({db_type})")
            logger.info("=" * 60)
            for table_name, col_count in tables.items():
                logger.info(f"  ✓ Table: {table_name:<25} ({col_count} columns)")
            logger.info("=" * 60)
            return True, db_type, tables

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        return False, str(e), {}
    finally:
        await engine.dispose()


if __name__ == "__main__":
    success, db_type, tables = asyncio.run(init_database())
    if not success:
        sys.exit(1)
