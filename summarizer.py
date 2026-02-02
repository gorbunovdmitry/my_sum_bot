"""
Модуль для суммаризации сообщений с использованием AI
Поддержка масштабирования и параллельной обработки
"""
import asyncio
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from config import settings
from database import Message as DBMessage
import hashlib
import json


class MessageSummarizer:
    """Суммаризация сообщений через AI с поддержкой масштабирования"""
    
    def __init__(self):
        self.use_openai = bool(settings.openai_api_key)
        self.use_local = bool(settings.local_model_path)
        self.cache = {} if settings.enable_caching else None
        self.executor = ThreadPoolExecutor(max_workers=settings.max_workers)
        
        if self.use_openai:
            self._init_openai()
        elif self.use_local:
            self._init_local_model()
        else:
            logger.warning("AI модель не настроена, будет использована простая суммаризация")
    
    def _init_openai(self):
        """Инициализация OpenAI"""
        try:
            import openai
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI клиент инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI: {e}")
            self.use_openai = False
    
    def _init_local_model(self):
        """Инициализация локальной модели с поддержкой MPS на Mac"""
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch
            
            # Определение устройства с приоритетом MPS для Mac
            device = "cpu"  # По умолчанию CPU
            
            if settings.use_mps and torch.backends.mps.is_available():
                device = "mps"
                device_name = "MPS (Apple Silicon)"
            elif torch.cuda.is_available():
                device = "cuda:0"
                device_name = "CUDA GPU"
            else:
                device_name = "CPU"
            
            logger.info(f"Использование устройства: {device_name}")
            
            # Загрузка модели и токенизатора
            logger.info(f"Загрузка модели {settings.local_model_path}...")
            self.tokenizer = AutoTokenizer.from_pretrained(settings.local_model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(settings.local_model_path)
            self.model.to(device)
            self.model.eval()
            self.device = device
            
            logger.info(f"Локальная модель {settings.local_model_path} загружена на {device_name}")
            logger.info(f"Параллельная обработка: {settings.max_workers} потоков")
        except Exception as e:
            logger.error(f"Ошибка загрузки локальной модели: {e}")
            self.use_local = False
    
    def _get_cache_key(self, messages: List[Dict]) -> str:
        """Создание ключа кэша из сообщений"""
        messages_str = json.dumps(
            [msg.get('text', '') for msg in messages[:50]],
            sort_keys=True
        )
        return hashlib.md5(messages_str.encode()).hexdigest()
    
    async def summarize_messages(
        self,
        messages: List[Dict],
        max_length: int = 150
    ) -> str:
        """
        Суммаризация списка сообщений с кэшированием
        """
        if not messages:
            return "Нет новых сообщений."
        
        # Проверка кэша
        if self.cache is not None:
            cache_key = self._get_cache_key(messages)
            if cache_key in self.cache:
                logger.debug(f"Использован кэш для ключа {cache_key[:8]}")
                return self.cache[cache_key]
        
        # Объединяем тексты сообщений
        texts = []
        for msg in messages:
            if msg.get('text'):
                texts.append(msg['text'])
        
        if not texts:
            return "Нет текстовых сообщений для суммаризации."
        
        combined_text = "\n".join(texts[:50])  # Максимум 50 сообщений
        
        # Обрезаем если слишком длинный (ограничения моделей)
        max_chars = 4000
        if len(combined_text) > max_chars:
            combined_text = combined_text[:max_chars] + "..."
        
        try:
            if self.use_openai:
                result = await self._summarize_openai(combined_text, max_length)
            elif self.use_local:
                result = await self._summarize_local(combined_text, max_length)
            else:
                result = self._summarize_simple(combined_text, max_length)
            
            # Сохранение в кэш
            if self.cache is not None:
                cache_key = self._get_cache_key(messages)
                self.cache[cache_key] = result
                # Очистка старого кэша (простая реализация)
                if len(self.cache) > 1000:
                    # Удаляем 20% старых записей
                    keys_to_remove = list(self.cache.keys())[:200]
                    for key in keys_to_remove:
                        del self.cache[key]
            
            return result
        except Exception as e:
            logger.error(f"Ошибка суммаризации: {e}")
            return self._summarize_simple(combined_text, max_length)
    
    def _summarize_sync(self, messages: List[Dict], max_length: int) -> str:
        """Синхронная обертка для суммаризации"""
        # Создаем новый event loop для синхронного выполнения
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.summarize_messages(messages, max_length))
    
    async def summarize_batch(
        self,
        messages_list: List[List[Dict]],
        max_length: int = 150
    ) -> List[str]:
        """
        Параллельная обработка батча запросов
        """
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                self.executor,
                self._summarize_sync,
                msgs,
                max_length
            )
            for msgs in messages_list
        ]
        return await asyncio.gather(*tasks)
    
    async def _summarize_openai(self, text: str, max_length: int) -> str:
        """Суммаризация через OpenAI"""
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты помощник для создания кратких сводок сообщений из Telegram. Создай краткую сводку основных тем и важных моментов."
                    },
                    {
                        "role": "user",
                        "content": f"Создай краткую сводку следующих сообщений (максимум {max_length} слов):\n\n{text}"
                    }
                ],
                max_tokens=max_length * 2,  # Примерно 2 токена на слово
                temperature=0.7
            )
            
            summary = response.choices[0].message.content
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Ошибка OpenAI суммаризации: {e}")
            return self._summarize_simple(text, max_length)
    
    def _summarize_local(self, text: str, max_length: int) -> str:
        """Суммаризация через локальную модель"""
        try:
            import torch
            
            # Токенизация входного текста
            inputs = self.tokenizer(
                text,
                max_length=1024,
                truncation=True,
                return_tensors="pt"
            ).to(self.device)
            
            # Генерация суммаризации
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    max_length=max_length,
                    min_length=max_length // 2,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            # Декодирование результата
            summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return summary
        except Exception as e:
            logger.error(f"Ошибка локальной суммаризации: {e}")
            return self._summarize_simple(text, max_length)
    
    def _summarize_simple(self, text: str, max_length: int) -> str:
        """Простая суммаризация (если AI недоступна)"""
        sentences = text.split('.')
        # Берем первые N предложений
        num_sentences = min(len(sentences), max_length // 20)
        summary = '. '.join(sentences[:num_sentences])
        if len(sentences) > num_sentences:
            summary += "..."
        return summary
    
    def group_by_topic(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Группировка сообщений по темам (простая реализация)
        Можно улучшить с помощью embeddings
        """
        topics = {}
        
        for msg in messages:
            # Простая группировка по ключевым словам
            # В реальности лучше использовать embeddings или кластеризацию
            text = msg.get('text', '').lower()
            
            # Определяем тему по ключевым словам
            topic = "Общее"
            if any(word in text for word in ['работа', 'задача', 'проект', 'встреча']):
                topic = "Работа"
            elif any(word in text for word in ['новости', 'событие', 'происшествие']):
                topic = "Новости"
            elif any(word in text for word in ['личное', 'семья', 'друзья']):
                topic = "Личное"
            
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(msg)
        
        return topics
