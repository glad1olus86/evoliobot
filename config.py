import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")  # URL вебхука Make.com для запроса кейсов
DB_PATH = os.getenv("DB_PATH", "bot.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Лимиты безопасности
MAX_PASSWORD_ATTEMPTS = 3
PASSWORD_BLOCK_SECONDS = 600   # 10 минут
FSM_TIMEOUT_SECONDS = 1800     # 30 минут

# Таймаут запроса к Make.com
MAKE_REQUEST_TIMEOUT = 30  # секунд (Make.com может быть медленным)

# Push-уведомления: вебхук-сервер
PUSH_WEBHOOK_PORT = int(os.getenv("PUSH_WEBHOOK_PORT", "8080"))
PUSH_WEBHOOK_SECRET = os.getenv("PUSH_WEBHOOK_SECRET", "evolio-push-secret-2024")
