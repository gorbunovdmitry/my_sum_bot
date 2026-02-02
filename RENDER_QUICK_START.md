# ⚡ Быстрый старт: Render.com (5 минут)

## 🚀 Шаги

### 1. Зарегистрируйтесь на Render
https://render.com (можно через GitHub)

### 2. Создайте Web Service

1. **New +** → **Web Service**
2. Подключите: `gorbunovdmitry/my_sum_bot`
3. Настройки:
   - **Name**: `telegram-summary-bot-auth`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python3 auth_server.py`

### 3. Добавьте переменные окружения

В разделе **Environment**:

```
TELEGRAM_API_ID=38193776
TELEGRAM_API_HASH=dec3b5f4c65a6b6f11d78490470c60be
BOT_TOKEN=8446491207:AAF-3mzeHGLs0XXgddODNmZI66gJK0Tqu4k
DATABASE_URL=sqlite:///./data/summary_bot.db
```

### 4. Создайте и дождитесь деплоя

Render автоматически:
- Установит зависимости
- Запустит сервер
- Даст публичный URL

Вы получите URL вида:
```
https://telegram-summary-bot-auth.onrender.com
```

### 5. Обновите index.html на GitHub

1. Откройте `index.html` в репозитории
2. Найдите: `const BACKEND_URL = 'https://ваш-бэкенд-домен.com/auth/callback';`
3. Замените на ваш Render URL:
   ```javascript
   const BACKEND_URL = 'https://telegram-summary-bot-auth.onrender.com/auth/callback';
   ```
4. Commit и push

### 6. Зарегистрируйте домен в BotFather

1. @BotFather → `/setdomain`
2. Выберите: `My_sum_test_bot`
3. Введите: `gorbunovdmitry.github.io`

### 7. Включите GitHub Pages

1. Settings → Pages → Source: main branch
2. Через несколько минут: https://gorbunovdmitry.github.io/my_sum_bot/

---

## ✅ Готово!

Теперь:
- Фронтенд: GitHub Pages
- Бэкенд: Render.com
- Домен зарегистрирован в BotFather

Кнопка "Login with Telegram" должна работать! 🎉

---

## ⚠️ Примечания

- На бесплатном плане Render "засыпает" после 15 минут бездействия
- Первый запрос после "сна" может занять 30-60 секунд
- Для продакшена рассмотрите платный план или другой хостинг
