"""
Простой тест бота для диагностики
"""
from bot import SummaryBot
from loguru import logger
import sys

logger.add(sys.stderr, level="DEBUG")

print("=" * 60)
print("Запуск бота для тестирования")
print("=" * 60)

bot = SummaryBot()

print(f"\n✅ Бот создан")
print(f"✅ Обработчиков команд: {len([h for h in bot.app.handlers[0] if hasattr(h, 'callback')])}")
print(f"\n🚀 Запуск бота...")
print("Отправьте команду /start боту в Telegram")
print("Нажмите Ctrl+C для остановки\n")

try:
    bot.run()
except KeyboardInterrupt:
    print("\n✅ Бот остановлен")
