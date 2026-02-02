#!/bin/bash

echo "🚀 Установка зависимостей для Telegram Summary Bot"
echo "=================================================="
echo ""

# Проверка Python
echo "📋 Проверка Python..."
python3 --version || { echo "❌ Python не найден!"; exit 1; }
echo "✅ Python установлен"
echo ""

# Установка зависимостей
echo "📦 Установка зависимостей..."
echo "Это может занять несколько минут..."
echo ""

pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Зависимости установлены успешно!"
else
    echo ""
    echo "❌ Ошибка при установке зависимостей"
    exit 1
fi

echo ""
echo "🧪 Проверка установки..."
echo ""

# Проверка основных модулей
python3 -c "import torch; print(f'✅ PyTorch {torch.__version__}')" || echo "❌ PyTorch не установлен"
python3 -c "import transformers; print(f'✅ Transformers {transformers.__version__}')" || echo "❌ Transformers не установлен"
python3 -c "import telegram; print(f'✅ python-telegram-bot установлен')" || echo "❌ python-telegram-bot не установлен"
python3 -c "import telethon; print(f'✅ Telethon установлен')" || echo "❌ Telethon не установлен"

echo ""
echo "🎯 Проверка MPS (Metal Performance Shaders) для Mac..."
python3 -c "import torch; print(f'✅ MPS доступен: {torch.backends.mps.is_available()}')" || echo "⚠️  MPS недоступен (это нормально для не-Mac)"

echo ""
echo "=================================================="
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Отредактируйте .env файл (добавьте TELEGRAM_API_ID, API_HASH, BOT_TOKEN)"
echo "2. Запустите: python3 setup_local_model.py"
echo "3. Запустите: python3 setup_user.py"
echo "4. Запустите: python3 main.py"
echo ""
