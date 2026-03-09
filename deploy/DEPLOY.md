# Деплой evolio-bot на Ubuntu VPS

---

## Шаг 0 — Загрузить файлы на сервер

С локальной машины (Windows):
```bash
scp -r C:\Users\Administrator\Desktop\WORK\advokat\evolio-bot root@ВАШ_IP:/tmp/evolio-bot
```

Или через git:
```bash
# На сервере:
git clone <ваш-репо> /tmp/evolio-bot
```

---

## Шаг 1 — Запуск установочного скрипта

```bash
ssh root@ВАШ_IP
cd /tmp/evolio-bot
sudo bash deploy/setup.sh
```

Скрипт сделает:
- Установит Python 3, pip, venv
- Создаст пользователя `evolio`
- Скопирует проект в `/opt/evolio-bot`
- Создаст venv и установит зависимости
- Создаст systemd-сервис

---

## Шаг 2 — Заполнить .env

```bash
sudo nano /opt/evolio-bot/.env
```

Вставить реальные значения:
```
BOT_TOKEN=123456:ABC...
CASES_PASSWORD=ваш_пароль
EVOLIO_WEBHOOK_URL=https://hookemachine.evolio.cz/hook/standard/2b01c45b-4383-4a3f-bbdd-782b7b3305e8
DB_PATH=/opt/evolio-bot/bot.db
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8443
```

---

## Шаг 3 — Запуск бота

```bash
sudo systemctl start evolio-bot
sudo systemctl status evolio-bot    # проверить что запустился
sudo journalctl -u evolio-bot -f    # логи в реальном времени
```

---

## Вариант А — По IP (без SSL, быстрый тест)

### А.1 Установить nginx

```bash
sudo apt install -y nginx
```

### А.2 Скопировать конфиг

```bash
sudo cp /tmp/evolio-bot/deploy/nginx-ip.conf /etc/nginx/sites-available/evolio-bot
sudo ln -s /etc/nginx/sites-available/evolio-bot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### А.3 Открыть порт 80

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### А.4 Проверить

```bash
curl http://ВАШ_IP/webhook/evolio \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"telegramId": 123, "idPripad": 1, "stavVyhledani": "Nalezen"}'
```

Должен вернуть: `{"ok": true}` или `{"ok": false, ...}`

### А.5 Callback URL для начальника

```
http://ВАШ_IP/webhook/evolio
```

> ⚠️ Если Evolio не принимает HTTP (требует HTTPS) — переходи к Варианту Б.

---

## Вариант Б — С доменом + SSL (продакшн)

### Б.1 Направить домен на VPS

В DNS-панели домена добавить A-запись:
```
Тип: A
Имя: bot (или @ для корневого)
Значение: ВАШ_IP
TTL: 300
```

Подождать 5–10 минут, проверить:
```bash
ping bot.your-domain.com
```

### Б.2 Установить nginx + certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Б.3 Скопировать конфиг

```bash
sudo cp /tmp/evolio-bot/deploy/nginx-domain.conf /etc/nginx/sites-available/evolio-bot
sudo ln -s /etc/nginx/sites-available/evolio-bot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

**Заменить `your-domain.com` на свой домен:**
```bash
sudo sed -i 's/your-domain.com/bot.ваш-домен.com/g' /etc/nginx/sites-available/evolio-bot
```

### Б.4 Получить SSL-сертификат

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# Сначала запускаем nginx без SSL (закомментировать server :443 или использовать ip-конфиг)
# Потом certbot сам настроит:
sudo certbot --nginx -d bot.ваш-домен.com
```

Certbot автоматически:
- Получит сертификат
- Настроит nginx на HTTPS
- Добавит автообновление

### Б.5 Проверить

```bash
sudo nginx -t
sudo systemctl reload nginx

curl https://bot.ваш-домен.com/webhook/evolio \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"telegramId": 123, "idPripad": 1, "stavVyhledani": "Nalezen"}'
```

### Б.6 Callback URL для начальника

```
https://bot.ваш-домен.com/webhook/evolio
```

---

## Полезные команды

```bash
# Статус бота
sudo systemctl status evolio-bot

# Логи бота (в реальном времени)
sudo journalctl -u evolio-bot -f

# Перезапуск бота после изменений
sudo systemctl restart evolio-bot

# Логи nginx
sudo tail -f /var/log/nginx/error.log

# Проверить что порт слушается
ss -tlnp | grep 8443

# Обновить код
cd /opt/evolio-bot
sudo -u evolio git pull   # если через git
sudo systemctl restart evolio-bot
```

---

## Что отправить начальнику

Одно из:
- **Вариант А:** `http://ВАШ_IP/webhook/evolio`
- **Вариант Б:** `https://bot.ваш-домен.com/webhook/evolio`

Начальнику нужно в Evolio в узле "Zavolat Webhook" указать этот URL.
И обязательно прокидывать поле `telegramId` из входящего запроса в callback.
