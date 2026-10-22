"""Idempotent, introspected migrations on the configured async engine only."""
import logging
from sqlalchemy import inspect, text, literal

logger = logging.getLogger(__name__)


async def run_migrations(engine):
    from app.database import Base
    from app import models
    async with engine.begin() as connection:
        if connection.dialect.name == 'postgresql':
            await connection.execute(text('SELECT pg_advisory_xact_lock(1450495052)'))
        elif connection.dialect.name == 'sqlite':
            await connection.execute(text('BEGIN IMMEDIATE'))
        # Create missing tables, then add only columns absent in existing tables.
        await connection.run_sync(Base.metadata.create_all)
        for table in Base.metadata.sorted_tables:
            columns = await connection.run_sync(lambda conn: {c['name'] for c in inspect(conn).get_columns(table.name)})
            quote = connection.dialect.identifier_preparer.quote
            for column in table.columns:
                if column.name in columns:
                    continue
                if column.primary_key:
                    raise RuntimeError(f"Cannot add missing primary key automatically: {table.name}.{column.name}")
                definition = column.type.compile(dialect=connection.dialect)
                default = None
                if column.default is not None and column.default.is_scalar:
                    default = column.default.arg
                # Nullable legacy records are backfilled before applying future
                # API invariants. Non-null scalar fields get a DB default.
                if default is not None:
                    encoded = str(literal(default).compile(dialect=connection.dialect, compile_kwargs={'literal_binds': True}))
                    definition += f" DEFAULT {encoded}"
                if not column.nullable and default is not None:
                    definition += " NOT NULL"
                await connection.execute(text(f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} {definition}"))
                logger.info('Migrated %s.%s', table.name, column.name)
            for index in table.indexes:
                if index.name == 'uq_subtitle_project_cue':
                    duplicates = await connection.scalar(text('SELECT COUNT(*) FROM (SELECT project_id, cue_index FROM subtitle_cues GROUP BY project_id, cue_index HAVING COUNT(*) > 1) AS duplicates'))
                    if duplicates:
                        raise RuntimeError('Duplicate subtitle indices in existing database; back up and repair duplicate project/cue_index rows before migration')
                await connection.run_sync(lambda conn, index=index: index.create(conn, checkfirst=True))
        # Legacy SQLite tables cannot acquire CHECK via ALTER TABLE. Equivalent
        # triggers enforce the same invariant without rebuilding or deleting data.
        invalid = await connection.scalar(text('SELECT COUNT(*) FROM subtitle_cues WHERE cue_index <= 0 OR start_time < 0 OR end_time <= start_time'))
        if invalid:
            raise RuntimeError('Invalid subtitle timing in existing database; back up and repair these cues before migration')
        if connection.dialect.name == 'sqlite':
            for event in ('INSERT', 'UPDATE'):
                await connection.execute(text(f"CREATE TRIGGER IF NOT EXISTS ck_subtitle_timing_{event.lower()} BEFORE {event} ON subtitle_cues WHEN NEW.cue_index <= 0 OR NEW.start_time < 0 OR NEW.end_time <= NEW.start_time BEGIN SELECT RAISE(ABORT, 'Invalid subtitle timing'); END"))
        elif connection.dialect.name == 'postgresql':
            checks = await connection.run_sync(lambda conn: {c['name'] for c in inspect(conn).get_check_constraints('subtitle_cues')})
            if 'ck_subtitle_timing' not in checks:
                await connection.execute(text('ALTER TABLE subtitle_cues ADD CONSTRAINT ck_subtitle_timing CHECK (cue_index > 0 AND start_time >= 0 AND end_time > start_time)'))
        await connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"))
        exists = await connection.scalar(text('SELECT version FROM schema_migrations WHERE version=1'))
        if exists is None:
            await connection.execute(text('INSERT INTO schema_migrations (version) VALUES (1)'))
        if await connection.scalar(text('SELECT version FROM schema_migrations WHERE version=2')) is None:
            await connection.execute(text('INSERT INTO schema_migrations (version) VALUES (2)'))
        if await connection.scalar(text('SELECT version FROM schema_migrations WHERE version=3')) is None:
            await connection.execute(text('INSERT INTO schema_migrations (version) VALUES (3)'))
