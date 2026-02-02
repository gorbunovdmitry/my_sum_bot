"""
Скрипт для тестирования масштабируемости на Mac M3 Pro
"""
import asyncio
import time
from summarizer import MessageSummarizer
from config import settings


async def test_scaling():
    """Тест масштабируемости"""
    
    print("=" * 60)
    print("Тест масштабируемости на Mac M3 Pro")
    print("=" * 60)
    
    # Проверка настроек
    print(f"\n📊 Настройки:")
    print(f"   Параллельных потоков: {settings.max_workers}")
    print(f"   Кэширование: {'Включено' if settings.enable_caching else 'Выключено'}")
    print(f"   Размер батча: {settings.batch_size}")
    
    # Инициализация суммаризатора
    print(f"\n🔄 Инициализация суммаризатора...")
    summarizer = MessageSummarizer()
    
    # Тестовые данные
    test_messages = [
        {"text": f"Это тестовое сообщение номер {i}. " * 10}
        for i in range(50)
    ]
    
    # Тест 1: Одиночный запрос
    print(f"\n📝 Тест 1: Одиночный запрос")
    start = time.time()
    result1 = await summarizer.summarize_messages(test_messages)
    elapsed1 = time.time() - start
    print(f"   Время: {elapsed1:.2f} секунд")
    print(f"   Результат: {result1[:100]}...")
    
    # Тест 2: Параллельная обработка
    print(f"\n📝 Тест 2: Параллельная обработка ({settings.max_workers} потоков)")
    batch = [test_messages] * settings.max_workers
    start = time.time()
    results = await summarizer.summarize_batch(batch)
    elapsed2 = time.time() - start
    print(f"   Время: {elapsed2:.2f} секунд")
    print(f"   Скорость: {settings.max_workers / elapsed2:.2f} запросов/сек")
    print(f"   Ускорение: {elapsed1 * settings.max_workers / elapsed2:.2f}x")
    
    # Тест 3: Кэширование
    if settings.enable_caching:
        print(f"\n📝 Тест 3: Кэширование")
        start = time.time()
        result_cached = await summarizer.summarize_messages(test_messages)
        elapsed3 = time.time() - start
        print(f"   Время (с кэшем): {elapsed3:.4f} секунд")
        print(f"   Ускорение: {elapsed1 / elapsed3:.0f}x")
    
    # Оценка пропускной способности
    print(f"\n" + "=" * 60)
    print("Оценка пропускной способности:")
    print("=" * 60)
    
    avg_time = elapsed2 / settings.max_workers
    requests_per_hour = 3600 / avg_time
    
    print(f"\n⏱️  Среднее время на запрос: {avg_time:.2f} секунд")
    print(f"📈 Пропускная способность: ~{requests_per_hour:.0f} запросов/час")
    print(f"👥 Максимум пользователей (1 запрос/день):")
    print(f"   - При пиковой нагрузке (1 час): ~{requests_per_hour:.0f}")
    print(f"   - При распределенной нагрузке: ~{requests_per_hour * 24:.0f}")
    
    # Рекомендации
    print(f"\n" + "=" * 60)
    print("Рекомендации:")
    print("=" * 60)
    
    if requests_per_hour >= 2000:
        print("✅ Отлично! Можете обслуживать до 2000+ пользователей")
    elif requests_per_hour >= 1000:
        print("✅ Хорошо! Можете обслуживать до 1000-2000 пользователей")
    elif requests_per_hour >= 500:
        print("⚠️  Приемлемо! Можете обслуживать до 500-1000 пользователей")
    else:
        print("❌ Низкая производительность. Рекомендуется оптимизация или API")
    
    if avg_time > 15:
        print("\n💡 Рекомендации по оптимизации:")
        print("   - Увеличьте количество потоков (max_workers)")
        print("   - Используйте более легкую модель")
        print("   - Включите кэширование")
        print("   - Рассмотрите использование API для пиковых нагрузок")


if __name__ == "__main__":
    asyncio.run(test_scaling())
