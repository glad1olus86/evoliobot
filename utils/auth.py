"""
Společná logika ověření hesla a ochrany proti brute-force.
"""

import hashlib
import hmac
import time

from config import MAX_PASSWORD_ATTEMPTS, PASSWORD_BLOCK_SECONDS

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
