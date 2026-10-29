import pytest
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_migration_uses_configured_database_and_is_idempotent(tmp_path):
    from app.database import Base
    from app.models import Project
    from app.services.db_migrator import run_migrations
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "old.db"}')
    async with engine.begin() as conn:
        await conn.execute(text('CREATE TABLE projects (id VARCHAR(36) PRIMARY KEY, title VARCHAR(255) NOT NULL)'))
        await conn.execute(text("INSERT INTO projects (id,title) VALUES ('old','keep me')"))
    await run_migrations(engine)
    await run_migrations(engine)
    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT title,user_id,active_job_id FROM projects WHERE id='old'"))).one()
        assert row.title == 'keep me' and row.user_id == 'local' and row.active_job_id is None
        names = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert 'jobs' in names and 'worker_leases' in names
    await engine.dispose()
