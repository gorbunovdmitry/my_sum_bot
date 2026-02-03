# 🚀 Настройка бэкенда на Render.com

## Шаг 1: Подготовка

1. Зарегистрируйтесь на https://render.com (можно через GitHub)
2. Убедитесь, что репозиторий https://github.com/gorbunovdmitry/my_sum_bot публичный или подключите приватный

## Шаг 2: Создание Web Service

1. В Dashboard Render нажмите **"New +"** → **"Web Service"**
2. Подключите репозиторий: `gorbunovdmitry/my_sum_bot`
3. Настройки:
   - **Name**: `telegram-summary-bot-auth`
   - **Region**: Выберите ближайший (например, Frankfurt)
   - **Branch**: `main`
   - **Root Directory**: оставьте пустым
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python3 auth_server.py`

## Шаг 3: Переменные окружения

В разделе **Environment Variables** добавьте:

```
TELEGRAM_API_ID=38193776
TELEGRAM_API_HASH=dec3b5f4c65a6b6f11d78490470c60be
BOT_TOKEN=8446491207:AAF-3mzeHGLs0XXgddODNmZI66gJK0Tqu4k
DATABASE_URL=sqlite:///./data/summary_bot.db
LOG_LEVEL=INFO
```

⚠️ **Важно**: Для продакшена лучше использовать PostgreSQL вместо SQLite.

## Шаг 4: Деплой

1. Нажмите **"Create Web Service"**
2. Render начнет деплой (займет 2-5 минут)
3. После успешного деплоя вы получите URL вида:
   ```
   https://telegram-summary-bot-auth.onrender.com
   ```

## Шаг 5: Обновите index.html

В вашем репозитории GitHub обновите `index.html`:

1. Откройте `index.html` на GitHub
2. Найдите строку:
   ```javascript
   const BACKEND_URL = 'https://ваш-бэкенд-домен.com/auth/callback';
   ```
3. Замените на ваш Render URL:
   ```javascript
   const BACKEND_URL = 'https://telegram-summary-bot-auth.onrender.com/auth/callback';
   ```
4. Commit и push изменения

## Шаг 6: Проверка

1. Откройте ваш Render URL: `https://telegram-summary-bot-auth.onrender.com/auth`
2. Должна открыться страница авторизации
3. Проверьте `/auth/callback` endpoint (должен вернуть 404 или ошибку метода, но не 500)

## ⚠️ Важные моменты

### SQLite на Render

SQLite может не работать на Render из-за файловой системы. Рекомендуется:

1. **Использовать PostgreSQL** (бесплатно на Render):
   - В Render создайте **PostgreSQL** database
   - Скопируйте **Internal Database URL**
   - Обновите `DATABASE_URL` в Environment Variables:
     ```
     DATABASE_URL=postgresql://user:pass@host:5432/dbname
     ```

2. Или использовать **внешнюю БД** (например, Supabase, Neon)

### Keep-Alive для бесплатного плана

На бесплатном плане Render "засыпает" после 15 минут бездействия. Для предотвращения:

1. Добавьте cron job для пинга (через GitHub Actions или внешний сервис)
2. Или используйте платный план Render

### CORS

Убедитесь, что `flask-cors` установлен (уже в requirements.txt).

---

## ✅ После настройки

1. ✅ Бэкенд работает на Render
2. ✅ Фронтенд на GitHub Pages
3. ✅ Обновите `BACKEND_URL` в `index.html`
4. ✅ Зарегистрируйте домен в BotFather

Готово! 🎉
