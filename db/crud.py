import aiosqlite
from config import DB_PATH


async def get_user(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_user(
    telegram_id: int, first_name: str, last_name: str, phone: str,
    password_hash: str = "",
) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id, first_name, last_name, phone, password_hash, is_registered)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (telegram_id, first_name, last_name, phone, password_hash),
        )
        await db.commit()
    return await get_user(telegram_id)


async def get_user_by_phone(phone: str) -> dict | None:
    """Najde uživatele podle telefonního čísla."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE phone = ? AND is_registered = 1", (phone,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def update_user(telegram_id: int, **fields) -> dict | None:
    if not fields:
        return await get_user(telegram_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [telegram_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE telegram_id = ?", values
        )
        await db.commit()
    return await get_user(telegram_id)


# ─── Dokumenty ───

async def save_document(
    case_id: str,
    telegram_id: int,
    filename: str,
    telegram_file_id: str,
    ukol_id: str | None = None,
) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO documents (case_id, ukol_id, telegram_id, filename, telegram_file_id)
               VALUES (?, ?, ?, ?, ?)""",
            (case_id, ukol_id, telegram_id, filename, telegram_file_id),
        )
        await db.commit()
        doc_id = cursor.lastrowid
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = await cur.fetchone()
        return dict(row)


async def get_document_by_id(doc_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_documents_by_case(case_id: str, telegram_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM documents
               WHERE case_id = ? AND telegram_id = ?
               ORDER BY created_at DESC""",
            (case_id, telegram_id),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_latest_documents_by_case(
    case_id: str, telegram_id: int, limit: int = 5
) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM documents
               WHERE case_id = ? AND telegram_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (case_id, telegram_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]
