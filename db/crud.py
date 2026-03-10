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
