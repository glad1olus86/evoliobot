"""
Společná logika ověření hesla a ochrany proti brute-force.
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import aiosqlite

from config import MAX_PASSWORD_ATTEMPTS, PASSWORD_BLOCK_SECONDS, DB_PATH

SESSION_DAYS = 3  # сессия без пароля — 3 дня

_password_attempts: dict[int, dict] = {}


def hash_password(password: str) -> str:
    """Vytvoří SHA-256 hash hesla."""
    return hashlib.sha256(password.encode()).hexdigest()


def check_blocked(telegram_id: int) -> float | None:
    """Vrátí zbývající sekundy blokace, nebo None pokud není blokován."""
    info = _password_attempts.get(telegram_id)
    if not info:
        return None
    blocked_until = info.get("blocked_until", 0)
    remaining = blocked_until - time.time()
    return remaining if remaining > 0 else None


def record_attempt(telegram_id: int, success: bool):
    """Zaznamená pokus o heslo. Při úspěchu resetuje počítadlo."""
    if success:
        _password_attempts.pop(telegram_id, None)
        return
    info = _password_attempts.setdefault(telegram_id, {"attempts": 0, "blocked_until": 0})
    info["attempts"] += 1
    if info["attempts"] >= MAX_PASSWORD_ATTEMPTS:
        info["blocked_until"] = time.time() + PASSWORD_BLOCK_SECONDS
        info["attempts"] = 0


def remaining_attempts(telegram_id: int) -> int:
    """Vrátí počet zbývajících pokusů."""
    info = _password_attempts.get(telegram_id, {})
    return MAX_PASSWORD_ATTEMPTS - info.get("attempts", 0)


def verify_password(entered: str, stored_hash: str) -> bool:
    """Bezpečné porovnání hesla s uloženým hashem (timing-safe)."""
    entered_hash = hash_password(entered)
    return hmac.compare_digest(entered_hash, stored_hash)


async def is_session_valid(telegram_id: int) -> bool:
    """Zkontroluje, zda má uživatel aktivní session (< SESSION_DAYS dní)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT password_verified_at FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if not row or not row["password_verified_at"]:
            return False
        verified_at = datetime.fromisoformat(row["password_verified_at"])
        if verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - verified_at < timedelta(days=SESSION_DAYS)


async def refresh_session(telegram_id: int):
    """Uloží aktuální čas jako password_verified_at."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET password_verified_at = ? WHERE telegram_id = ?",
            (now, telegram_id),
        )
        await db.commit()
