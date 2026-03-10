"""
Точка входа: aiogram polling + aiohttp webhook server для push-уведомлений.
Make.com используется как API — простые HTTP-запросы, без callback-сервера.
Gemini 2.5 Flash — AI чат-ассистент.
"""

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN, PUSH_WEBHOOK_PORT
from db.models import init_db
from handlers import start, menu, cases, chat
from services.push_server import create_push_app


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialized")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(cases.router)
    dp.include_router(chat.router)
    dp.include_router(menu.router)  # menu последним — fallback для /menu

    # Установить команды в меню бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Spustit bota"),
        BotCommand(command="menu", description="Hlavní menu"),
    ])

    # Запустить webhook-сервер для push-уведомлений
    push_app = create_push_app(bot)
    runner = web.AppRunner(push_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PUSH_WEBHOOK_PORT)
    await site.start()
    logger.info("Push webhook server started on port %s", PUSH_WEBHOOK_PORT)

    # Запустить polling
    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
