"""
Webhook server pro push notifikace z Make.com.

Make.com posílá POST na /webhook/push s daty o případu.
Server najde klienta podle telefonu v DB a odešle notifikaci do DM.
Podporuje i příjem dokumentů (base64 PDF) a jejich odeslání jako Telegram soubory.
"""

import base64
import logging
import re

from aiohttp import web
from aiogram.types import BufferedInputFile

from config import PUSH_WEBHOOK_PORT, PUSH_WEBHOOK_SECRET
from db.crud import get_user_by_phone, save_document

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str) -> str:
    """Nechá pouze číslice a úvodní +."""
    return re.sub(r"[^\d+]", "", phone)


def _format_notification(data: dict, user: dict) -> str:
    """Vytvoří HTML zprávu pro Telegram."""
    klient = f"{user['first_name']} {user['last_name']}"
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


TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB


def _extract_documents(data: dict) -> list[dict]:
    """Extrahuje dokumenty z payloadu. Vrací list of {"nazev": str, "base64": str}."""
    docs = []

    # Массив dokumenty на верхнем уровне
    if "dokumenty" in data and isinstance(data["dokumenty"], list):
        for item in data["dokumenty"]:
            if isinstance(item, dict):
                nazev = item.get("dokument_nazev", "document.pdf")
                b64 = item.get("dokument_base64", "")
                if b64:
                    docs.append({"nazev": nazev, "base64": b64})

    # Вложенная структура ukol.Dokumenty
    ukol = data.get("ukol")
    if isinstance(ukol, dict) and "Dokumenty" in ukol:
        doku = ukol["Dokumenty"]
        if isinstance(doku, list):
            for item in doku:
                if isinstance(item, dict):
                    nazev = item.get("dokument_nazev", item.get("Nazev", "document.pdf"))
                    b64 = item.get("dokument_base64", item.get("Base64", ""))
                    if b64:
                        docs.append({"nazev": nazev, "base64": b64})

    # Один документ на верхнем уровне
    if not docs:
        b64 = data.get("dokument_base64", "")
        if b64:
            nazev = data.get("dokument_nazev", "document.pdf")
            docs.append({"nazev": nazev, "base64": b64})

    return docs


def _extract_ids(data: dict) -> tuple[str | None, str | None]:
    """Extrahuje idPripad a idUkol z payloadu."""
    case_id = data.get("idPripad")
    ukol_id = data.get("idUkol")

    if not case_id:
        pripad = data.get("pripad")
        if isinstance(pripad, dict):
            case_id = pripad.get("IdPripad") or pripad.get("idPripad")

    if not ukol_id:
        ukol = data.get("ukol")
        if isinstance(ukol, dict):
            ukol_id = ukol.get("IdUkol") or ukol.get("idUkol")

    return str(case_id) if case_id else None, str(ukol_id) if ukol_id else None


async def _send_document(bot, telegram_id: int, doc: dict) -> str | None:
    """Dekóduje base64 a odešle jako Telegram dokument. Vrací file_id nebo None."""
    nazev = doc["nazev"]
    try:
        file_bytes = base64.b64decode(doc["base64"])
    except Exception as e:
        logger.error("Failed to decode base64 for %s: %s", nazev, e)
        return None

    if len(file_bytes) == 0:
        logger.warning("Document %s is empty, skipping", nazev)
        return None

    if len(file_bytes) > TELEGRAM_FILE_SIZE_LIMIT:
        logger.warning("Document %s too large (%d bytes), skipping", nazev, len(file_bytes))
        return None

    try:
        input_file = BufferedInputFile(file_bytes, filename=nazev)
        result = await bot.send_document(
            chat_id=telegram_id,
            document=input_file,
            caption=f"📎 {nazev}",
        )
        return result.document.file_id
    except Exception as e:
        logger.error("Failed to send document %s to %s: %s", nazev, telegram_id, e)
        return None


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
    html_message = _format_notification(data, user)
    bot = request.app["bot"]

    # Извлекаем документы и ID
    documents = _extract_documents(data)
    case_id, ukol_id = _extract_ids(data)

    # Отправка текстового уведомления
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=html_message,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("Failed to send push to %s: %s", telegram_id, e)
        return web.json_response({"error": str(e)}, status=500)

    # Отправка документов (если есть)
    if documents:
        sent_count = 0
        for doc in documents:
            file_id = await _send_document(bot, telegram_id, doc)
            if file_id and case_id:
                await save_document(
                    case_id=case_id,
                    telegram_id=telegram_id,
                    filename=doc["nazev"],
                    telegram_file_id=file_id,
                    ukol_id=ukol_id,
                )
                sent_count += 1
        logger.info(
            "Push with %d/%d doc(s) sent to telegram_id=%s (case=%s)",
            sent_count, len(documents), telegram_id, case_id,
        )
        return web.json_response({
            "ok": True,
            "telegram_id": telegram_id,
            "documents_sent": sent_count,
        })

    logger.info("Push sent to telegram_id=%s", telegram_id)
    return web.json_response({"ok": True, "telegram_id": telegram_id})


def create_push_app(bot) -> web.Application:
    """Создаёт aiohttp приложение для push-вебхука."""
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook/push", handle_push)
    return app
