#!/bin/bash
# ============================================
# Установка evolio-bot на Ubuntu VPS
# Запуск: sudo bash setup.sh
# ============================================

set -e

APP_DIR="/opt/evolio-bot"
APP_USER="evolio"

echo "=== [1/5] Установка системных пакетов ==="
apt update
apt install -y python3 python3-pip python3-venv

echo "=== [2/5] Создание пользователя ==="
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/false "$APP_USER"
    echo "Пользователь $APP_USER создан"
else
    echo "Пользователь $APP_USER уже существует"
fi

echo "=== [3/5] Копирование файлов ==="
mkdir -p "$APP_DIR"
cp -r bot.py config.py requirements.txt handlers/ services/ db/ utils/ "$APP_DIR/"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "=== [4/5] Создание виртуального окружения ==="
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "=== [5/5] Настройка .env и systemd ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << 'ENVEOF'
BOT_TOKEN=ВСТАВЬ_ТОКЕН_БОТА
CASES_PASSWORD=ВСТАВЬ_ПАРОЛЬ
MAKE_WEBHOOK_URL=ВСТАВЬ_URL_ВЕБХУКА_MAKE_COM
DB_PATH=/opt/evolio-bot/bot.db
ENVEOF
    echo ""
    echo "!!! ОТРЕДАКТИРУЙ /opt/evolio-bot/.env !!!"
    echo "    nano /opt/evolio-bot/.env"
fi
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

cat > /etc/systemd/system/evolio-bot.service << 'EOF'
[Unit]
Description=Evolio Telegram Bot
After=network.target

[Service]
Type=simple
User=evolio
WorkingDirectory=/opt/evolio-bot
ExecStart=/opt/evolio-bot/venv/bin/python bot.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/evolio-bot/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable evolio-bot

echo ""
echo "============================================"
echo "  Установка завершена!"
echo "============================================"
echo ""
echo "  1. Отредактируй .env:  nano /opt/evolio-bot/.env"
echo "  2. Запусти бота:       sudo systemctl start evolio-bot"
echo "  3. Логи:               sudo journalctl -u evolio-bot -f"
echo ""
echo "  Nginx НЕ нужен — бот работает через polling."
echo ""
