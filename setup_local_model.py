"""
Скрипт для тестирования локальной модели и проверки производительности
"""
import time
import sys
from transformers import pipeline
import torch


def test_model_performance(model_name: str = "facebook/bart-large-cnn"):
    """Тест производительности локальной модели"""
    import torch
    
    print("=" * 60)
    print("Тест производительности локальной модели")
    print("=" * 60)
    
    # Проверка доступности GPU/MPS
    has_cuda = torch.cuda.is_available()
    has_mps = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
    has_gpu = has_cuda or has_mps
    
    if has_cuda:
        device_name = "CUDA GPU"
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\n✅ Обнаружен CUDA GPU: {gpu_name}")
        print(f"   Память GPU: {gpu_memory:.1f} GB")
    elif has_mps:
        device_name = "MPS (Apple Silicon)"
        print(f"\n✅ Обнаружен MPS (Metal Performance Shaders)")
        print(f"   Apple Silicon GPU будет использоваться")
    else:
        device_name = "CPU"
        print(f"\n⚠️  GPU не обнаружен, будет использоваться CPU")
    
    print(f"\n📦 Загрузка модели: {model_name}")
    print("   Это может занять 1-3 минуты при первом запуске...")
    
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch
        
        device = "mps" if has_gpu and torch.backends.mps.is_available() else "cpu"
        print(f"   Использование устройства: {device}")
        
        print("   Загрузка токенизатора...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print("   Загрузка модели...")
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        model.to(device)
        model.eval()
        
        print("✅ Модель загружена успешно!")
        
        # Сохраняем для тестирования
        summarizer = {
            'tokenizer': tokenizer,
            'model': model,
            'device': device
        }
    except Exception as e:
        print(f"❌ Ошибка загрузки модели: {e}")
        return False
    
    # Тестовые данные разного размера
    test_cases = [
        ("Короткий текст", 100, "Это тестовое сообщение. " * 10),
        ("Средний текст", 500, "Это тестовое сообщение. " * 50),
        ("Длинный текст", 1000, "Это тестовое сообщение. " * 100),
        ("Очень длинный текст", 2000, "Это тестовое сообщение. " * 200),
    ]
    
    print("\n" + "=" * 60)
    print("Тестирование производительности:")
    print("=" * 60)
    
    results = []
    
    for name, word_count, text in test_cases:
        print(f"\n📝 Тест: {name} (~{word_count} слов)")
        
        start_time = time.time()
        try:
            import torch
            
            # Токенизация
            inputs = summarizer['tokenizer'](
                text,
                max_length=1024,
                truncation=True,
                return_tensors="pt"
            ).to(summarizer['device'])
            
            # Генерация
            with torch.no_grad():
                outputs = summarizer['model'].generate(
                    inputs["input_ids"],
                    max_length=100,
                    min_length=50,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            # Декодирование
            summary = summarizer['tokenizer'].decode(outputs[0], skip_special_tokens=True)
            elapsed = time.time() - start_time
            print(f"   ⏱️  Время обработки: {elapsed:.2f} секунд")
            print(f"   📊 Скорость: {word_count/elapsed:.1f} слов/сек")
            print(f"   ✅ Результат: {summary[:80]}...")
            
            results.append({
                'name': name,
                'words': word_count,
                'time': elapsed,
                'speed': word_count / elapsed
            })
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            results.append({
                'name': name,
                'words': word_count,
                'time': None,
                'speed': None
            })
    
    # Итоговая оценка
    print("\n" + "=" * 60)
    print("Итоговая оценка:")
    print("=" * 60)
    
    avg_speed = sum(r['speed'] for r in results if r['speed']) / len([r for r in results if r['speed']])
    
    print(f"\n📈 Средняя скорость: {avg_speed:.1f} слов/секунду")
    
    # Оценка для реального использования
    typical_words = 5000  # Типичный объем для сводки
    estimated_time = typical_words / avg_speed if avg_speed > 0 else None
    
    if estimated_time:
        print(f"\n⏱️  Оценка для типичной сводки (~{typical_words} слов):")
        print(f"   Время обработки: ~{estimated_time:.0f} секунд ({estimated_time/60:.1f} минут)")
        
        if estimated_time < 30:
            print("   ✅ Отлично! Можно использовать для ежедневных сводок")
        elif estimated_time < 60:
            print("   ✅ Хорошо! Приемлемая скорость")
        elif estimated_time < 120:
            print("   ⚠️  Медленно, но работает. Рассмотрите использование API")
        else:
            print("   ❌ Слишком медленно. Рекомендуется использовать API")
    
    # Рекомендации
    print("\n" + "=" * 60)
    print("Рекомендации:")
    print("=" * 60)
    
    if has_gpu:
        print("\n✅ У вас есть GPU - отлично!")
        print("   Модель будет работать быстро")
    else:
        print("\n⚠️  GPU не обнаружен")
        print("   Модель будет работать на CPU (медленнее)")
        print("   Рекомендация: Рассмотрите использование API для скорости")
    
    print("\n💡 Для использования в боте:")
    print(f"   1. Добавьте в .env: LOCAL_MODEL_PATH={model_name}")
    print("   2. Оставьте OPENAI_API_KEY пустым")
    print("   3. Запустите бота: python main.py")
    
    return True


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "facebook/bart-large-cnn"
    test_model_performance(model)
