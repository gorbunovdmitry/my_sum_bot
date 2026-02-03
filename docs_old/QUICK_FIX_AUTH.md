# ⚡ БЫСТРОЕ РЕШЕНИЕ: Запустить auth локально

## Проблема
SQLite на Render не работает, поэтому авторизация не сохраняется.

## Решение: Запустить auth_server локально

### Шаг 1: Установите ngrok (если еще не установлен)

```bash
# macOS
brew install ngrok

# Или скачайте с https://ngrok.com/download
```

### Шаг 2: Запустите auth_server локально

Откройте новый терминал:

```bash
cd telegram_summary_bot
python3 auth_server.py
```

Оставьте его запущенным.

### Шаг 3: Запустите ngrok в другом терминале

```bash
ngrok http 5000
```

Скопируйте HTTPS URL (например: `https://abc123.ngrok-free.app`)

### Шаг 4: Обновите index.html на GitHub

1. Откройте `index.html` в репозитории на GitHub
2. Найдите строку:
   ```javascript
   const BACKEND_URL = 'https://telegram-summary-bot-auth.onrender.com/auth/callback';
   ```
3. Замените на ваш ngrok URL:
   ```javascript
   const BACKEND_URL = 'https://abc123.ngrok-free.app/auth/callback';
   ```
4. Commit и push изменения

### Шаг 5: Обновите домен в BotFather

1. Откройте @BotFather в Telegram
2. Отправьте `/setdomain`
3. Выберите: `My_sum_test_bot`
4. Введите ngrok домен (без https://): `abc123.ngrok-free.app`

### Шаг 6: Перезапустите бота

```bash
pkill -f "python3 main.py"
python3 main.py
```

### Шаг 7: Проверьте авторизацию

1. Отправьте боту `/auth`
2. Откройте ссылку (теперь она будет использовать ngrok)
3. Авторизуйтесь через "Login with Telegram"
4. Отправьте `/status` - должен показать "✅ Авторизован"

## Важно

⚠️ **ngrok URL меняется при каждом перезапуске!**

Если перезапустите ngrok, нужно будет:
1. Обновить `BACKEND_URL` в `index.html`
2. Обновить домен в BotFather

Для постоянного URL используйте ngrok с авторизацией или настройте PostgreSQL на Render.

## Альтернатива: PostgreSQL на Render

Для постоянного решения настройте PostgreSQL на Render (см. SOLUTION_AUTH.md).
