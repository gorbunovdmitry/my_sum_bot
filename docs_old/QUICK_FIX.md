# ⚡ Быстрое решение проблемы "bot domain invalid"

## Проблема
Telegram требует зарегистрированный домен для Login Widget.

## Решение: Использовать ngrok

### Быстрый старт:

1. **Установите ngrok** (если еще не установлен):
   ```bash
   brew install ngrok/ngrok/ngrok
   ```

2. **Получите токен** на https://dashboard.ngrok.com/get-started/your-authtoken

3. **Настройте токен**:
   ```bash
   ngrok config add-authtoken YOUR_TOKEN
   ```

4. **Запустите туннель** (в отдельном терминале):
   ```bash
   ngrok http 5000
   ```

5. **Скопируйте URL** вида: `https://xxxx-xx-xx-xx-xx.ngrok-free.app`

6. **Зарегистрируйте домен в BotFather**:
   - Откройте @BotFather в Telegram
   - Отправьте: `/setdomain`
   - Выберите бота: `My_sum_test_bot`
   - Введите домен (без https://): `xxxx-xx-xx-xx-xx.ngrok-free.app`

7. **Обновите .env файл**:
   ```bash
   echo "AUTH_SERVER_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app/auth" >> .env
   ```
   (замените на ваш ngrok URL)

8. **Перезапустите бота**

9. **Откройте в браузере**: `https://xxxx-xx-xx-xx-xx.ngrok-free.app/auth`

✅ Готово! Кнопка должна появиться.

## Важно

- ngrok должен быть запущен пока работает бот
- При каждом перезапуске ngrok URL может измениться (если используете бесплатный план)
- Для продакшена лучше использовать постоянный домен
