"""
Главный модуль приложения
Объединяет Client API для сканирования и Bot API для доставки
"""
import asyncio
from loguru import logger
from config import settings
from telegram_client import SafeTelegramClient
from scheduler import SafeScheduler
from summarizer import MessageSummarizer
from bot import SummaryBot
from database import User, Channel, Message, Summary, SessionLocal
from datetime import datetime


class SummaryBotApp:
    """Главное приложение бота"""
    
    def __init__(self):
        self.telegram_clients = {}  # user_id -> SafeTelegramClient
        self.summarizer = MessageSummarizer()
        self.scheduler = SafeScheduler()
        self.bot = SummaryBot(app_instance=self)  # Передаем ссылку на приложение
    
    async def scan_user_chats(self, user_id: int):
        """
        Сканирование чатов для конкретного пользователя
        """
        logger.info(f"Начало сканирования для пользователя {user_id}")
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(id=user_id).first()
            
            if not user:
                logger.error(f"Пользователь {user_id} не найден")
                return
            
            # Проверяем, что пользователь авторизован и включен
            if not user.is_authorized:
                logger.info(f"Пользователь {user_id} не авторизован, пропускаем")
                return
            
            if not user.is_enabled:
                logger.info(f"Пользователь {user_id} выключен, пропускаем")
                return
            
            # Получаем или создаем клиент
            if user_id not in self.telegram_clients:
                if not user.phone:
                    logger.error(f"У пользователя {user_id} не указан телефон")
                    return
                
                client = SafeTelegramClient(user_id, user.phone)
                if not await client.connect():
                    logger.error(f"Не удалось подключиться для пользователя {user_id}")
                    return
                
                self.telegram_clients[user_id] = client
            else:
                client = self.telegram_clients[user_id]
            
            # Получаем активные каналы пользователя
            active_channels = [
                c for c in user.channels 
                if c.is_active
            ]
            
            if not active_channels:
                logger.info(f"Нет активных каналов для пользователя {user_id}")
                return
            
            # Получаем ID чатов для сканирования
            chat_ids = [c.telegram_chat_id for c in active_channels[:settings.max_chats_per_scan]]
            
            # Сканируем чаты безопасно
            messages_by_chat = await client.scan_chats_safe(
                chat_ids,
                max_chats=settings.max_chats_per_scan
            )
            
            # Сохраняем сообщения в БД
            all_messages = []
            for chat_id, messages in messages_by_chat.items():
                db_channel = db.query(Channel).filter_by(
                    telegram_chat_id=chat_id,
                    user_id=user_id
                ).first()
                
                if not db_channel:
                    continue
                
                for msg in messages:
                    if msg.text:
                        db_message = Message(
                            channel_id=db_channel.id,
                            telegram_message_id=msg.id,
                            text=msg.text,
                            author=getattr(msg.sender, 'first_name', None) or 'Unknown',
                            timestamp=msg.date,
                            message_type='text'
                        )
                        db.add(db_message)
                        all_messages.append({
                            'text': msg.text,
                            'author': db_message.author,
                            'timestamp': db_message.timestamp
                        })
                
                db.commit()
            
            # Создаем сводку
            if all_messages:
                summary_text = await self.summarizer.summarize_messages(all_messages)
                topics = list(self.summarizer.group_by_topic(all_messages).keys())
                
                summary = Summary(
                    user_id=user_id,
                    date=datetime.utcnow(),
                    summary_text=summary_text,
                    topics=topics,
                    channels_included=[c.telegram_chat_id for c in active_channels]
                )
                db.add(summary)
                db.commit()
                
                # Отправляем сводку через бота
                await self.bot.send_summary(user.telegram_id, summary_text)
                
                logger.info(f"Сводка создана и отправлена для пользователя {user_id}")
            else:
                logger.info(f"Нет новых сообщений для пользователя {user_id}")
        finally:
            db.close()
    
    async def scan_all_users(self):
        """Сканирование для всех активных пользователей"""
        db = SessionLocal()
        try:
            # Сканируем только для пользователей с включенным ботом
            users = db.query(User).filter_by(is_enabled=True, is_authorized=True).all()
        finally:
            db.close()
        
        for user in users:
            try:
                await self.scan_user_chats(user.id)
                # Задержка между пользователями
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Ошибка сканирования для пользователя {user.id}: {e}")
                continue
    
    async def run_scheduler(self):
        """Запуск планировщика"""
        async def scan_callback():
            await self.scan_all_users()
        
        await self.scheduler.schedule_daily_scan(scan_callback)
    
    def run(self):
        """Запуск приложения"""
        import threading
        
        logger.info("Запуск Telegram Summary Bot...")
        
        # Запускаем веб-сервер авторизации в отдельном потоке
        def run_auth_server():
            try:
                from auth_server import app
                app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            except Exception as e:
                logger.error(f"Ошибка веб-сервера авторизации: {e}")
        
        auth_server_thread = threading.Thread(target=run_auth_server, daemon=True)
        auth_server_thread.start()
        logger.info("Веб-сервер авторизации запущен на http://localhost:5000")
        
        # Запускаем планировщик в отдельном потоке
        def run_scheduler_thread():
            try:
                asyncio.run(self.run_scheduler())
            except Exception as e:
                logger.error(f"Ошибка планировщика: {e}")
        
        scheduler_thread = threading.Thread(target=run_scheduler_thread, daemon=True)
        scheduler_thread.start()
        
        # Запускаем бота в основном потоке (блокирующий вызов)
        try:
            # bot.run() - синхронный метод, не нужно asyncio.run
            self.bot.run()
        except KeyboardInterrupt:
            logger.info("Остановка приложения...")
            self.scheduler.stop()
            for client in self.telegram_clients.values():
                try:
                    asyncio.run(client.disconnect())
                except:
                    pass


if __name__ == "__main__":
    # Настройка логирования
    logger.add(
        settings.log_file,
        rotation="1 day",
        retention="7 days",
        level=settings.log_level
    )
    
    app = SummaryBotApp()
    
    try:
        app.run()  # run() - синхронный метод, не нужен asyncio.run
    except KeyboardInterrupt:
        logger.info("Приложение остановлено")
