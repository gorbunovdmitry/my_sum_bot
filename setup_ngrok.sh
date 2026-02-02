#!/bin/bash
# Скрипт для настройки ngrok для Telegram Login Widget

echo "🔧 Настройка ngrok для Telegram Login Widget"
echo ""

# Проверяем наличие ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok не установлен"
    echo ""
    echo "Установите ngrok:"
    echo "1. Скачайте с https://ngrok.com/download"
    echo "2. Или через Homebrew: brew install ngrok/ngrok/ngrok"
    echo ""
    echo "После установки получите токен на https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "И выполните: ngrok config add-authtoken YOUR_TOKEN"
    exit 1
fi

echo "✅ ngrok найден"
echo ""
echo "Запускаю туннель на порт 5000..."
echo "После запуска вы получите публичный URL вида: https://xxxx-xx-xx-xx-xx.ngrok-free.app"
echo ""
echo "Этот URL нужно будет:"
echo "1. Скопировать"
echo "2. Отправить боту @BotFather команду: /setdomain"
echo "3. Выбрать вашего бота"
echo "4. Ввести домен (без https://, например: xxxx-xx-xx-xx-xx.ngrok-free.app)"
echo ""

# Запускаем ngrok
ngrok http 5000
