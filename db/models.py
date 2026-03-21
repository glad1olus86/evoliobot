import aiosqlite
from config import DB_PATH

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    password_hash TEXT NOT NULL DEFAULT '',
    is_registered BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Миграция: добавить password_hash если таблица уже существует
MIGRATION_ADD_PASSWORD = """
ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT '';
"""

MIGRATION_ADD_VERIFIED_AT = """
ALTER TABLE users ADD COLUMN password_verified_at DATETIME DEFAULT NULL;
"""

CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    ukol_id TEXT DEFAULT NULL,
    telegram_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    telegram_file_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_DOCUMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_documents_case_telegram
ON documents(case_id, telegram_id);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_DOCUMENTS_TABLE)
        await db.execute(CREATE_DOCUMENTS_INDEX)
        # Миграции — если колонки ещё не существуют
        for migration in (MIGRATION_ADD_PASSWORD, MIGRATION_ADD_VERIFIED_AT):
            try:
                await db.execute(migration)
            except Exception:
                pass
        await db.commit()
