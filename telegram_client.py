"""
Безопасный клиент для работы с Telegram Client API
Реализует все рекомендации по снижению риска блокировки
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel, Message as TgMessage
from loguru import logger
from config import settings
from database import Channel as DBChannel, Message as DBMessage, get_db


class SafeTelegramClient:
    """Безопасный клиент Telegram с защитой от блокировки"""
    
    def __init__(self, user_id: int, phone: str = None):
        self.user_id = user_id
        self.phone = phone
        self.client: Optional[TelegramClient] = None
        self.session_file = settings.session_dir / f"user_{user_id}.session"
        
    async def connect(self, phone: str = None) -> bool:
        """Подключение к Telegram"""
        try:
            if phone:
                self.phone = phone
            
            if not self.phone:
                logger.error(f"Телефон не указан для пользователя {self.user_id}")
                return False
            
            self.client = TelegramClient(
                str(self.session_file),
                settings.telegram_api_id,
                settings.telegram_api_hash
            )
            
            # Если сессия существует, пробуем подключиться без кода
            if self.session_file.exists():
                try:
                    await self.client.start()
                    logger.info(f"Подключение через сессию для пользователя {self.user_id}")
                    return True
                except:
                    # Сессия невалидна, нужна авторизация
                    pass
            
            # Нужна авторизация
            if self.phone:
                await self.client.start(phone=self.phone)
                logger.info(f"Успешное подключение для пользователя {self.user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от Telegram"""
        if self.client:
            await self.client.disconnect()
            logger.info(f"Отключение для пользователя {self.user_id}")
    
    async def get_user_dialogs(self) -> List[Dict]:
        """Получить список диалогов пользователя"""
        if not self.client:
            raise RuntimeError("Клиент не подключен")
        
        try:
            dialogs = await self.client.get_dialogs()
            result = []
            
            for dialog in dialogs:
                entity = dialog.entity
                chat_info = {
                    'id': entity.id,
                    'title': getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown'),
                    'type': self._get_chat_type(entity),
                    'unread_count': dialog.unread_count,
                    'last_message_date': dialog.date
                }
                result.append(chat_info)
            
            logger.info(f"Получено {len(result)} диалогов для пользователя {self.user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения диалогов: {e}")
            return []
    
    def _get_chat_type(self, entity) -> str:
        """Определить тип чата"""
        if isinstance(entity, User):
            return 'private'
        elif isinstance(entity, Chat):
            return 'group'
        elif isinstance(entity, Channel):
            if entity.megagroup:
                return 'supergroup'
            return 'channel'
        return 'unknown'
    
    async def get_messages_safe(
        self,
        chat_id: int,
        limit: int = 100,
        offset_date: Optional[datetime] = None
    ) -> List[TgMessage]:
        """
        Безопасное получение сообщений с задержками и обработкой ошибок
        """
        if not self.client:
            raise RuntimeError("Клиент не подключен")
        
        try:
            # Случайная задержка перед запросом
            delay = random.uniform(
                settings.scan_delay_min_seconds,
                settings.scan_delay_max_seconds
            )
            await asyncio.sleep(delay)
            
            # Получение сообщений
            messages = await self.client.get_messages(
                chat_id,
                limit=limit,
                offset_date=offset_date
            )
            
            logger.debug(f"Получено {len(messages)} сообщений из чата {chat_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из чата {chat_id}: {e}")
            # Обработка FLOOD_WAIT
            if "FLOOD_WAIT" in str(e):
                wait_time = self._extract_flood_wait_time(str(e))
                logger.warning(f"FLOOD_WAIT: ожидание {wait_time} секунд")
                await asyncio.sleep(wait_time)
            return []
    
    def _extract_flood_wait_time(self, error_msg: str) -> int:
        """Извлечь время ожидания из FLOOD_WAIT ошибки"""
        try:
            # Формат: FLOOD_WAIT_X где X - секунды
            import re
            match = re.search(r'FLOOD_WAIT_(\d+)', error_msg)
            if match:
                return int(match.group(1)) + 1  # +1 для запаса
        except:
            pass
        return 60  # По умолчанию 60 секунд
    
    async def scan_chats_safe(
        self,
        chat_ids: List[int],
        max_chats: Optional[int] = None
    ) -> Dict[int, List[TgMessage]]:
        """
        Безопасное сканирование чатов с учетом всех рекомендаций:
        - Ограничение количества
        - Случайный порядок
        - Задержки между запросами
        - Инкрементальное обновление
        """
        if not self.client:
            raise RuntimeError("Клиент не подключен")
        
        # Ограничение количества чатов
        if max_chats:
            chat_ids = chat_ids[:max_chats]
        
        # Случайный порядок обработки
        random.shuffle(chat_ids)
        
        results = {}
        request_count = 0
        
        for i, chat_id in enumerate(chat_ids):
            try:
                # Получаем время последнего сканирования из БД
                from database import SessionLocal
                db = SessionLocal()
                try:
                    db_channel = db.query(DBChannel).filter_by(
                        telegram_chat_id=chat_id,
                        user_id=self.user_id
                    ).first()
                    
                    offset_date = None
                    if db_channel and db_channel.last_scan_time:
                        offset_date = db_channel.last_scan_time
                    
                    # Получаем только новые сообщения
                    messages = await self.get_messages_safe(
                        chat_id,
                        limit=100,
                        offset_date=offset_date
                    )
                    
                    if messages:
                        results[chat_id] = messages
                    
                    # Обновляем время последнего сканирования
                    if db_channel:
                        db_channel.last_scan_time = datetime.utcnow()
                        db.commit()
                finally:
                    db.close()
                
                request_count += 1
                
                # Контроль частоты запросов
                if request_count >= settings.max_requests_per_second:
                    logger.info("Достигнут лимит запросов, пауза 1 секунда")
                    await asyncio.sleep(1)
                    request_count = 0
                
                # Дополнительная задержка между чатами
                if i < len(chat_ids) - 1:  # Не для последнего
                    delay = random.uniform(0.5, 2.0)
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Ошибка сканирования чата {chat_id}: {e}")
                continue
        
        logger.info(f"Сканирование завершено: {len(results)} чатов обработано")
        return results
