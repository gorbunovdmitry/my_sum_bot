"""
Планировщик безопасного сканирования с вариацией времени
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from config import settings


class SafeScheduler:
    """Планировщик с защитой от детекции"""
    
    def __init__(self):
        self.running = False
        self.tasks = []
    
    def get_next_scan_time(self) -> datetime:
        """
        Получить время следующего сканирования с вариацией
        """
        now = datetime.now()
        
        # Базовое время сегодня
        base_time = now.replace(
            hour=settings.scan_base_hour,
            minute=settings.scan_base_minute,
            second=0,
            microsecond=0
        )
        
        # Если базовое время уже прошло, планируем на завтра
        if base_time < now:
            base_time += timedelta(days=1)
        
        # Добавляем случайную вариацию (±N минут)
        variation_minutes = random.randint(
            -settings.scan_time_variation_minutes,
            settings.scan_time_variation_minutes
        )
        
        scan_time = base_time + timedelta(minutes=variation_minutes)
        
        # Добавляем случайные секунды для большей вариации
        scan_time = scan_time.replace(
            second=random.randint(0, 59)
        )
        
        logger.info(f"Следующее сканирование запланировано на: {scan_time}")
        return scan_time
    
    def should_skip_scan(self) -> bool:
        """
        Определить, нужно ли пропустить сканирование (имитация человеческого поведения)
        """
        if random.random() < settings.skip_scan_probability:
            logger.info("Пропуск сканирования (имитация человеческого поведения)")
            return True
        return False
    
    async def wait_until(self, target_time: datetime):
        """Ожидание до указанного времени"""
        while datetime.now() < target_time:
            wait_seconds = (target_time - datetime.now()).total_seconds()
            # Ждем максимум 60 секунд за раз, чтобы можно было остановить
            wait_seconds = min(wait_seconds, 60)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
    
    async def schedule_daily_scan(self, scan_callback):
        """
        Планирование ежедневного сканирования с безопасными интервалами
        """
        self.running = True
        
        while self.running:
            try:
                # Проверяем, нужно ли пропустить сканирование
                if self.should_skip_scan():
                    # Планируем на следующий день
                    next_time = self.get_next_scan_time()
                    await self.wait_until(next_time)
                    continue
                
                # Получаем время следующего сканирования
                next_scan_time = self.get_next_scan_time()
                
                # Ждем до времени сканирования
                await self.wait_until(next_scan_time)
                
                # Выполняем сканирование
                if self.running:
                    logger.info("Начало запланированного сканирования")
                    await scan_callback()
                    logger.info("Сканирование завершено")
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                # В случае ошибки ждем час перед следующей попыткой
                await asyncio.sleep(3600)
    
    def stop(self):
        """Остановка планировщика"""
        self.running = False
        logger.info("Планировщик остановлен")
