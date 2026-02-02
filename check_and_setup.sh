#!/bin/bash
# Скрипт для проверки и настройки ngrok

echo "🔍 Проверка настройки Telegram Login Widget"
echo ""

# Проверяем ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok не установлен"
    echo ""
    echo "Установите ngrok:"
    echo "  brew install ngrok/ngrok/ngrok"
    echo ""
    echo "Затем получите токен на https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "И выполните: ngrok config add-authtoken YOUR_TOKEN"
    exit 1
fi

echo "✅ ngrok установлен"

# Проверяем, запущен ли ngrok
if lsof -ti:4040 &> /dev/null; then
    echo "✅ ngrok запущен"
    
    # Получаем URL туннеля
    TUNNEL_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tunnels = d.get('tunnels', [])
    for t in tunnels:
        if 'https' in t.get('public_url', ''):
            print(t['public_url'])
            break
except:
    pass
" 2>/dev/null)
    
    if [ -n "$TUNNEL_URL" ]; then
        echo "✅ Туннель активен: $TUNNEL_URL"
        echo ""
        echo "📋 Следующие шаги:"
        echo "1. Зарегистрируйте домен в @BotFather:"
        echo "   /setdomain → My_sum_test_bot → $(echo $TUNNEL_URL | sed 's|https://||' | sed 's|/auth||')"
        echo ""
        echo "2. Обновите .env:"
        echo "   echo 'AUTH_SERVER_URL=$TUNNEL_URL/auth' >> .env"
        echo ""
        echo "3. Перезапустите бота"
    else
        echo "⚠️  ngrok запущен, но туннель не найден"
        echo "   Запустите: ngrok http 5000"
    fi
else
    echo "❌ ngrok не запущен"
    echo ""
    echo "Запустите в отдельном терминале:"
    echo "  ngrok http 5000"
    echo ""
    echo "Затем запустите этот скрипт снова"
fi
