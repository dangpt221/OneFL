"""Initialize/migrate only the configured OneFL database; never change DSNs."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.database import init_db, engine


async def main():
    try:
        await init_db()
        print('Configured database initialized and migrated successfully.')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
