import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "onefl_videotrans.db"

def run_migrations():
    """Ensure all required columns exist in SQLite tables."""
    if not DB_PATH.exists():
        logger.info(f"Database at {DB_PATH} does not exist yet. Skipping column migrations.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Check and add columns to speaker_profiles
    cursor.execute("PRAGMA table_info(speaker_profiles)")
    spk_cols = [row[1] for row in cursor.fetchall()]

    if "original_name" not in spk_cols:
        cursor.execute("ALTER TABLE speaker_profiles ADD COLUMN original_name VARCHAR(100)")
        logger.info("Added column original_name to speaker_profiles")

    if "aliases" not in spk_cols:
        cursor.execute("ALTER TABLE speaker_profiles ADD COLUMN aliases VARCHAR(200)")
        logger.info("Added column aliases to speaker_profiles")

    if "avatar_color" not in spk_cols:
        cursor.execute("ALTER TABLE speaker_profiles ADD COLUMN avatar_color VARCHAR(20) DEFAULT '#6366f1'")
        logger.info("Added column avatar_color to speaker_profiles")

    # 2. Check and add columns to glossaries
    cursor.execute("PRAGMA table_info(glossaries)")
    glo_cols = [row[1] for row in cursor.fetchall()]

    if "priority" not in glo_cols:
        cursor.execute("ALTER TABLE glossaries ADD COLUMN priority VARCHAR(20) DEFAULT 'normal'")
        logger.info("Added column priority to glossaries")

    if "case_sensitive" not in glo_cols:
        cursor.execute("ALTER TABLE glossaries ADD COLUMN case_sensitive VARCHAR(10) DEFAULT 'false'")
        logger.info("Added column case_sensitive to glossaries")

    conn.commit()
    conn.close()
    logger.info("Database migration completed successfully.")

if __name__ == "__main__":
    run_migrations()
    print("Migration executed successfully.")
