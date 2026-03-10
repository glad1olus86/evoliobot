"""
Webhook server pro push notifikace z Make.com.

Make.com posílá POST na /webhook/push s daty o případu.
Server najde klienta podle telefonu v DB a odešle notifikaci do DM.
"""

import logging
import re

from aiohttp import web

from config import PUSH_WEBHOOK_PORT, PUSH_WEBHOOK_SECRET
from db.crud import get_user_by_phone

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    """Nechá pouze číslice a úvodní +."""
    return re.sub(r"[^\d+]", "", phone)


def _format_notification(data: dict) -> str:
    """Vytvoří HTML zprávu pro Telegram."""
    klient = data.get("klientJmeno", "")
    cislo = data.get("pripadCislo", "")
    nazev = data.get("pripadNazev", "")
    predmet = data.get("predmet", "")
    detail = data.get("detail", "")
    termin = data.get("termin", "")

    lines = ["🔔 <b>NOTIFIKACE PRO KLIENTA</b>\n"]

    if klient:
        lines.append(f"Vážený/á <b>{klient}</b>,\n")

    if cislo or nazev:
        case_info = f"č. {cislo}" if cislo else ""
        if nazev:
            case_info = f"{case_info} — {nazev}" if case_info else nazev
        lines.append(
            f"naše kancelář aktivně pracuje na Vašem případu <b>{case_info}</b>. "
            "V současné chvíli byl stav Vašeho případu aktualizován "
            "a obsahuje následující informace:\n"
        )

    if predmet:
        lines.append(f"📋 <b>Předmět:</b> {predmet}")
    if detail:
        lines.append(f"📄 <b>Detail:</b>\n{detail}")
    if termin:
        lines.append(f"📅 <b>Datum aktualizace:</b> {termin}")

    lines.append(
        "\n━━━━━━━━━━━━━━━━━━━━━\n"
        "📞 (+420) 732 394 849\n"
        "✉️ info@modernipravnik.cz\n"
        "🕐 Po–Pá 9:00–18:00\n\n"
        '📅 <a href="https://calendar.app.google/5uMEKH4TLEKK2kLd7">Sjednat si schůzku</a>'
    )

    return "\n".join(lines)


async def handle_push(request: web.Request) -> web.Response:
    """Обработчик POST /webhook/push от Make.com."""
    # Проверка секрета
    secret = request.headers.get("X-Webhook-Secret", "")
    if secret != PUSH_WEBHOOK_SECRET:
        logger.warning("Push webhook: invalid secret")
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    phone_raw = data.get("klientTelefon", "")
    if not phone_raw:
        return web.json_response({"error": "klientTelefon is required"}, status=400)

    phone = _normalize_phone(phone_raw)
    logger.info("Push notification for phone: %s", phone)

    # Поиск юзера по телефону
    user = await get_user_by_phone(phone)
    if not user:
        logger.warning("Push: user not found for phone %s", phone)
        return web.json_response({"error": "user not found", "phone": phone}, status=404)

    telegram_id = user["telegram_id"]
    html_message = _format_notification(data)

    # Отправка через бота (bot передаётся в app при запуске)
    bot = request.app["bot"]
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=html_message,
            disable_web_page_preview=True,
        )
        logger.info("Push sent to telegram_id=%s", telegram_id)
        return web.json_response({"ok": True, "telegram_id": telegram_id})
    except Exception as e:
        logger.error("Failed to send push to %s: %s", telegram_id, e)
        return web.json_response({"error": str(e)}, status=500)


def create_push_app(bot) -> web.Application:
    """Создаёт aiohttp приложение для push-вебхука."""
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook/push", handle_push)
    return app
