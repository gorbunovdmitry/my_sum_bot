# ✅ РЕШЕНИЕ: Бот не видит авторизацию

## Проблема
Авторизация проходит успешно на GitHub Pages → Render, но бот не видит авторизацию и просит авторизоваться снова.

## Причина
**SQLite на Render НЕ РАБОТАЕТ!** Файловая система на Render read-only, поэтому БД не сохраняет данные.

## Решение: Использовать одну PostgreSQL БД

Нужно настроить PostgreSQL на Render и использовать одну БД для обоих сервисов (auth на Render и бот локально).

### Шаг 1: Создайте PostgreSQL на Render

1. Откройте https://dashboard.render.com
2. **New +** → **PostgreSQL**
3. Название: `telegram-summary-bot-db`
4. План: **Free** (для начала)
5. **Create Database**

### Шаг 2: Получите Database URL

1. Откройте созданную базу данных
2. В разделе **Connections** → **Internal Database URL**
3. Скопируйте URL (например: `postgresql://user:pass@host:5432/dbname`)

### Шаг 3: Обновите Render Web Service

1. Откройте Web Service: `telegram-summary-bot-auth`
2. Перейдите в **Environment**
3. Найдите `DATABASE_URL`
4. Замените значение на PostgreSQL URL из шага 2
5. **Save Changes**
6. Render автоматически перезапустит сервис (подождите 2-5 минут)

### Шаг 4: Обновите локальный .env

Откройте файл `.env` в проекте и обновите:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**ВАЖНО**: Используйте тот же URL, что и на Render!

### Шаг 5: Перезапустите бота

```bash
cd telegram_summary_bot
pkill -f "python3 main.py"
python3 main.py
```

### Шаг 6: Проверьте авторизацию

1. Отправьте боту `/start` (если еще не отправляли)
2. Отправьте `/auth`
3. Откройте ссылку и авторизуйтесь через "Login with Telegram"
4. Отправьте `/status` - должен показать "✅ Авторизован"

## Альтернативное решение: Запустить auth локально

Если не хотите использовать PostgreSQL, можно запустить auth_server локально:

### Шаг 1: Остановите auth на Render

Или просто не используйте его.

### Шаг 2: Запустите auth локально

```bash
cd telegram_summary_bot
python3 auth_server.py
```

### Шаг 3: Используйте ngrok для публичного доступа

```bash
ngrok http 5000
```

Скопируйте HTTPS URL (например: `https://abc123.ngrok-free.app`)

### Шаг 4: Обновите index.html на GitHub

1. Откройте `index.html` в репозитории
2. Найдите: `const BACKEND_URL = 'https://telegram-summary-bot-auth.onrender.com/auth/callback';`
3. Замените на ваш ngrok URL: `const BACKEND_URL = 'https://abc123.ngrok-free.app/auth/callback';`
4. Commit и push

### Шаг 5: Обновите домен в BotFather

1. @BotFather → `/setdomain`
2. Выберите бота
3. Введите ngrok домен (без https://): `abc123.ngrok-free.app`

### Шаг 6: Перезапустите бота

```bash
pkill -f "python3 main.py"
python3 main.py
```

Теперь оба сервиса используют одну локальную SQLite БД.

## Проверка

После настройки PostgreSQL:

```bash
# Проверка health
curl https://telegram-summary-bot-auth.onrender.com/health

# Проверка авторизации (замените USER_ID на ваш Telegram ID)
curl https://telegram-summary-bot-auth.onrender.com/check-auth/107544557
```

Ваш Telegram ID можно узнать у @userinfobot в Telegram.

## Если все еще не работает

1. Проверьте логи Render: Dashboard → ваш сервис → **Logs**
2. Проверьте логи бота: `tail -f logs/bot.log`
3. Убедитесь, что PostgreSQL URL правильный
4. Проверьте, что таблицы созданы (должны создаться автоматически при первом запуске)
