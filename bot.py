"""
Основной модуль бота для доставки сводок через Bot API
Управление через команды в Telegram
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from loguru import logger
from config import settings
from database import User, Summary, Channel
import asyncio
import shutil
from pathlib import Path
from telegram_client import SafeTelegramClient
from telethon import TelegramClient


class SummaryBot:
    """Бот для доставки сводок с управлением через команды"""
    
    def __init__(self, app_instance=None):
        self.app = Application.builder().token(settings.bot_token).build()
        self.app_instance = app_instance  # Ссылка на главное приложение
        self._register_handlers()
        self.auth_clients = {}  # Временные клиенты для авторизации
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        # Команды
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("auth", self.auth))
        self.app.add_handler(CommandHandler("enable", self.enable))
        self.app.add_handler(CommandHandler("disable", self.disable))
        self.app.add_handler(CommandHandler("summary", self.get_summary))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("chats", self.list_chats))
        
        # Обработка сообщений (для авторизации)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработка callback кнопок
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def _check_auth_from_server(self, user_id: int) -> dict:
        """Проверка авторизации через auth server API"""
        try:
            import requests
            # Используем Render URL напрямую
            auth_server_url = "https://telegram-summary-bot-auth.onrender.com"
            check_url = f"{auth_server_url}/check-auth/{user_id}"
            
            logger.info(f"Проверка авторизации через API: {check_url}")
            response = requests.get(check_url, timeout=5)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Статус авторизации от API: {result}")
                return result
            else:
                logger.warning(f"API вернул статус {response.status_code}")
        except Exception as e:
            logger.warning(f"Не удалось проверить авторизацию через API: {e}")
        return None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user_id = update.effective_user.id
        logger.info(f"Получена команда /start от пользователя {user_id}")
        
        # Регистрируем пользователя в БД
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                user = User(telegram_id=user_id)
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Создан новый пользователь {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обработке /start: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
            return
        finally:
            db.close()
        
        # Проверяем авторизацию через API (если бот работает локально, а auth на Render)
        auth_status = await self._check_auth_from_server(user_id)
        if auth_status and auth_status.get('authorized'):
            # Синхронизируем статус из удаленной БД
            if not user.is_authorized:
                user.is_authorized = True
                user.auth_state = auth_status.get('auth_state', 'done')
                db.commit()
                logger.info(f"Синхронизирован статус авторизации для пользователя {user_id}")
        
        # Проверяем статус авторизации
        if not user.is_authorized:
            welcome_text = """
🤖 Добро пожаловать в Telegram Summary Bot!

Этот бот поможет вам получать ежедневные сводки из ваших чатов и каналов.

🔐 Для начала работы необходимо авторизоваться:
Используйте команду /auth для авторизации через ваш Telegram аккаунт.

После авторизации вы сможете:
✅ Включить/выключить бота командой /enable или /disable
✅ Выбрать чаты для сканирования
✅ Получать ежедневные сводки автоматически

📋 Все команды: /help
            """
        else:
            status_icon = "🟢" if user.is_enabled else "🔴"
            welcome_text = f"""
🤖 Добро пожаловать обратно!

{status_icon} Статус: {'Включен' if user.is_enabled else 'Выключен'}

📋 Доступные команды:
/enable - Включить бота
/disable - Выключить бота
/summary - Получить последнюю сводку
/status - Подробный статус
/chats - Управление чатами
/help - Справка
            """
        
        await update.message.reply_text(welcome_text)
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        help_text = """
📖 Справка по использованию бота:

🔐 Авторизация:
/auth - Авторизоваться через Telegram аккаунт

⚙️ Управление:
/enable - Включить бота (начать сканирование)
/disable - Выключить бота (остановить сканирование)
/status - Проверить статус и настройки

📊 Сводки:
/summary - Получить последнюю сводку за сегодня

📁 Чаты:
/chats - Управление чатами для сканирования

⚠️ Безопасность:
Бот использует безопасные паттерны сканирования:
- Вариация времени (±30 минут)
- Инкрементальное обновление
- Ограничение количества чатов
- Случайные задержки между запросами
        """
        
        await update.message.reply_text(help_text)
    
    async def auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать процесс авторизации через Telegram Login Widget"""
        user_id = update.effective_user.id
        logger.info(f"Получена команда /auth от пользователя {user_id}")
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                logger.warning(f"Пользователь {user_id} не найден в БД")
                await update.message.reply_text("❌ Сначала используйте /start")
                return
            
            # Проверяем авторизацию через API (синхронизация с Render)
            auth_status = await self._check_auth_from_server(user_id)
            if auth_status and auth_status.get('authorized'):
                # Синхронизируем статус
                if not user.is_authorized:
                    user.is_authorized = True
                    user.auth_state = auth_status.get('auth_state', 'done')
                    db.commit()
                    logger.info(f"Синхронизирован статус авторизации для пользователя {user_id}")
            
            # Проверяем авторизацию через API (синхронизация с Render)
            auth_status = await self._check_auth_from_server(user_id)
            if auth_status and auth_status.get('authorized'):
                # Синхронизируем статус
                if not user.is_authorized:
                    user.is_authorized = True
                    user.auth_state = auth_status.get('auth_state', 'done')
                    db.commit()
                    logger.info(f"Синхронизирован статус авторизации для пользователя {user_id}")
            
            if user.is_authorized:
                logger.info(f"Пользователь {user_id} уже авторизован")
                await update.message.reply_text(
                    "✅ Вы уже авторизованы!\n"
                    "Используйте /enable чтобы включить бота."
                )
                return
            
            # Используем GitHub Pages URL (фронтенд)
            auth_url = "https://gorbunovdmitry.github.io/my_sum_bot/"
            
            # Проверяем, доступен ли веб-сервер
            import requests
            try:
                response = requests.get(auth_url, timeout=2)
                server_available = response.status_code == 200
            except:
                server_available = False
            
            if server_available:
                await update.message.reply_text(
                    "🔐 Авторизация через Telegram Login Widget\n\n"
                    f"📱 Откройте ссылку в браузере:\n\n"
                    f"🔗 {auth_url}\n\n"
                    "На открывшейся странице нажмите кнопку \"Login with Telegram\" для авторизации.\n\n"
                    "✅ Это официальный способ авторизации, который не блокируется Telegram.",
                    disable_web_page_preview=False
                )
            else:
                await update.message.reply_text(
                    "🔐 Авторизация через Telegram Login Widget\n\n"
                    f"⚠️ Веб-сервер авторизации не доступен.\n\n"
                    f"Попробуйте открыть в браузере:\n{auth_url}\n\n"
                    "Или проверьте, что веб-сервер запущен.",
                    disable_web_page_preview=False
                )
                logger.warning(f"Веб-сервер авторизации не доступен для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка в команде /auth: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Произошла ошибка: {e}\n\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        finally:
            db.close()
    
    async def _wait_for_qr_auth(self, user_id: int, update: Update):
        """Ожидание завершения QR-авторизации"""
        from database import SessionLocal
        
        try:
            temp_client = self.auth_clients.get(user_id)
            if not temp_client:
                return
            
            # Ждем авторизации через QR-код (максимум 5 минут)
            # Проверяем статус авторизации периодически
            for i in range(60):  # Проверяем каждые 5 секунд в течение 5 минут
                try:
                    # Проверяем, авторизован ли клиент
                    if await temp_client.is_user_authorized():
                        logger.info(f"Пользователь {user_id} успешно авторизован через QR-код")
                        break
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Ошибка проверки авторизации: {e}")
                    await asyncio.sleep(5)
            else:
                raise asyncio.TimeoutError("Время ожидания QR-авторизации истекло (5 минут)")
            
            # Финальная проверка
            if not await temp_client.is_user_authorized():
                raise Exception("Авторизация не завершена")
            
            # Авторизация успешна
            db = SessionLocal()
            try:
                user = db.query(User).filter_by(telegram_id=user_id).first()
                if not user:
                    return
                
                # Сохраняем сессию
                import shutil
                temp_session = settings.session_dir / f"temp_qr_{user_id}.session"
                final_session = settings.session_dir / f"user_{user.id}.session"
                if temp_session.exists():
                    shutil.copy(temp_session, final_session)
                
                # Получаем информацию о пользователе
                me = await temp_client.get_me()
                user.phone = me.phone
                user.is_authorized = True
                user.auth_state = 'done'
                user.pending_phone = None
                db.commit()
                
                # Закрываем временный клиент
                await temp_client.disconnect()
                del self.auth_clients[user_id]
                if hasattr(self, 'qr_data'):
                    self.qr_data.pop(user_id, None)
                
                # Удаляем временную сессию
                if temp_session.exists():
                    temp_session.unlink()
                
                await update.message.reply_text(
                    "✅ Авторизация успешна!\n\n"
                    "Теперь вы можете:\n"
                    "/enable - Включить бота\n"
                    "/chats - Выбрать чаты для сканирования"
                )
            finally:
                db.close()
                
        except asyncio.TimeoutError:
            await update.message.reply_text(
                "⏱️ Время ожидания истекло. Попробуйте /auth еще раз."
            )
        except Exception as e:
            logger.error(f"Ошибка QR-авторизации: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка авторизации: {e}\n\n"
                "Попробуйте еще раз: /auth"
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (для авторизации)"""
        user_id = update.effective_user.id
        text = update.message.text
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user or not user.auth_state:
                return  # Игнорируем, если не в процессе авторизации
            
            # QR-авторизация не требует текстового ввода
            if user.auth_state == 'qr':
                await update.message.reply_text(
                    "⏳ Ожидаю сканирования QR-кода...\n\n"
                    "Откройте Telegram на телефоне и отсканируйте QR-код, который я отправил."
                )
                return
            
            # Старая логика с телефоном (оставлена для совместимости, но не используется)
            if user.auth_state == 'phone':
                # Сохраняем телефон и запрашиваем код
                user.pending_phone = text
                user.auth_state = 'code'
                db.commit()
                
                # Создаем временный клиент для авторизации
                from telethon import TelegramClient
                temp_session_file = settings.session_dir / f"temp_auth_{user_id}.session"
                
                try:
                    temp_client = TelegramClient(
                        str(temp_session_file),
                        settings.telegram_api_id,
                        settings.telegram_api_hash
                    )
                    
                    await temp_client.connect()
                    await temp_client.send_code_request(text)
                    
                    # Сохраняем клиент для дальнейшего использования
                    self.auth_clients[user_id] = temp_client
                    
                    await update.message.reply_text(
                        "✅ Код подтверждения отправлен в Telegram!\n\n"
                        "Введите код, который вы получили:"
                    )
                except Exception as e:
                    logger.error(f"Ошибка запроса кода: {e}", exc_info=True)
                    await update.message.reply_text(
                        f"❌ Ошибка: {e}\n\n"
                        "Попробуйте еще раз: /auth"
                    )
                    user.auth_state = None
                    db.commit()
                    # Закрываем клиент при ошибке
                    if user_id in self.auth_clients:
                        try:
                            await self.auth_clients[user_id].disconnect()
                        except:
                            pass
                        del self.auth_clients[user_id]
            
            elif user.auth_state == 'code':
                # Проверяем код
                try:
                    code = text.strip()
                    temp_client = self.auth_clients.get(user_id)
                    
                    if not temp_client:
                        await update.message.reply_text(
                            "❌ Сессия авторизации истекла. Попробуйте /auth еще раз"
                        )
                        user.auth_state = None
                        db.commit()
                        return
                    
                    # Авторизуемся
                    await temp_client.sign_in(user.pending_phone, code)
                    
                    # Сохраняем сессию в правильное место
                    import shutil
                    temp_session = settings.session_dir / f"temp_auth_{user_id}.session"
                    final_session = settings.session_dir / f"user_{user.id}.session"
                    if temp_session.exists():
                        shutil.copy(temp_session, final_session)
                    
                    # Сохраняем успешную авторизацию
                    user.phone = user.pending_phone
                    user.is_authorized = True
                    user.auth_state = 'done'
                    user.pending_phone = None
                    db.commit()
                    
                    # Закрываем временный клиент
                    await temp_client.disconnect()
                    del self.auth_clients[user_id]
                    
                    # Удаляем временную сессию
                    if temp_session.exists():
                        temp_session.unlink()
                    
                    await update.message.reply_text(
                        "✅ Авторизация успешна!\n\n"
                        "Теперь вы можете:\n"
                        "/enable - Включить бота\n"
                        "/chats - Выбрать чаты для сканирования"
                    )
                except Exception as e:
                    logger.error(f"Ошибка авторизации: {e}")
                    await update.message.reply_text(
                        f"❌ Неверный код или ошибка: {e}\n\n"
                        "Попробуйте еще раз: /auth"
                    )
                    user.auth_state = None
                    db.commit()
        finally:
            db.close()
    
    async def enable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Включить бота для пользователя"""
        user_id = update.effective_user.id
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала используйте /start")
                return
            
            if not user.is_authorized:
                await update.message.reply_text(
                    "❌ Сначала авторизуйтесь: /auth"
                )
                return
            
            if user.is_enabled:
                await update.message.reply_text(
                    "✅ Бот уже включен!\n"
                    "Используйте /status для проверки статуса."
                )
                return
            
            user.is_enabled = True
            db.commit()
            
            await update.message.reply_text(
                "✅ Бот включен!\n\n"
                "Бот будет автоматически сканировать ваши чаты каждый день "
                f"в {settings.scan_base_hour}:{settings.scan_base_minute:02d} (±{settings.scan_time_variation_minutes} мин)\n\n"
                "Используйте /chats чтобы выбрать чаты для сканирования."
            )
        finally:
            db.close()
    
    async def disable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выключить бота для пользователя"""
        user_id = update.effective_user.id
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                await update.message.reply_text("❌ Сначала используйте /start")
                return
            
            if not user.is_enabled:
                await update.message.reply_text(
                    "ℹ️ Бот уже выключен."
                )
                return
            
            user.is_enabled = False
            db.commit()
            
            await update.message.reply_text(
                "🔴 Бот выключен.\n\n"
                "Сканирование остановлено. Используйте /enable чтобы включить снова."
            )
        finally:
            db.close()
    
    async def list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список и управление чатами"""
        user_id = update.effective_user.id
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user or not user.is_authorized:
                await update.message.reply_text(
                    "❌ Сначала авторизуйтесь: /auth"
                )
                return
            
            # Получаем список чатов пользователя через Client API
            if self.app_instance:
                # Используем клиент из главного приложения
                client = self.app_instance.telegram_clients.get(user.id)
                if not client:
                    # Создаем клиент если его нет
                    client = SafeTelegramClient(user.id, user.phone)
                    if await client.connect():
                        self.app_instance.telegram_clients[user.id] = client
                    else:
                        await update.message.reply_text(
                            "❌ Не удалось подключиться. Попробуйте /auth еще раз."
                        )
                        return
                
                # Получаем список диалогов
                dialogs = await client.get_user_dialogs()
                
                if not dialogs:
                    await update.message.reply_text("📭 Чаты не найдены.")
                    return
                
                # Формируем список
                text = "📁 Ваши чаты и каналы:\n\n"
                keyboard = []
                
                for i, dialog in enumerate(dialogs[:20]):  # Показываем первые 20
                    is_active = db.query(Channel).filter_by(
                        telegram_chat_id=dialog['id'],
                        user_id=user.id
                    ).first() is not None
                    
                    icon = "✅" if is_active else "⚪"
                    text += f"{icon} {dialog['title']}\n"
                    
                    keyboard.append([InlineKeyboardButton(
                        f"{'🔴 Отключить' if is_active else '🟢 Включить'} {dialog['title'][:30]}",
                        callback_data=f"chat_{dialog['id']}_{'off' if is_active else 'on'}"
                    )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    text + "\nИспользуйте кнопки для включения/выключения чатов.",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "⚠️ Функция временно недоступна. "
                    "Управление чатами будет доступно после полной настройки."
                )
        finally:
            db.close()
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith("chat_"):
            # Обработка включения/выключения чата
            parts = data.split("_")
            chat_id = int(parts[1])
            action = parts[2]
            
            from database import SessionLocal
            db = SessionLocal()
            try:
                user = db.query(User).filter_by(telegram_id=user_id).first()
                
                if not user:
                    return
                
                channel = db.query(Channel).filter_by(
                    telegram_chat_id=chat_id,
                    user_id=user.id
                ).first()
                
                if action == 'on':
                    if not channel:
                        # Получаем название чата
                        chat_title = "Unknown"
                        if self.app_instance:
                            client = self.app_instance.telegram_clients.get(user.id)
                            if client:
                                dialogs = await client.get_user_dialogs()
                                for d in dialogs:
                                    if d['id'] == chat_id:
                                        chat_title = d['title']
                                        break
                        
                        channel = Channel(
                            user_id=user.id,
                            telegram_chat_id=chat_id,
                            title=chat_title,
                            chat_type='unknown',
                            is_active=True
                        )
                        db.add(channel)
                    else:
                        channel.is_active = True
                    
                    db.commit()
                    await query.edit_message_text(
                        f"✅ Чат '{channel.title}' включен для сканирования"
                    )
                else:
                    if channel:
                        channel.is_active = False
                        db.commit()
                        await query.edit_message_text(
                            f"🔴 Чат '{channel.title}' выключен"
                        )
            finally:
                db.close()
    
    async def get_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получить последнюю сводку"""
        user_id = update.effective_user.id
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                await update.message.reply_text(
                    "❌ Вы не зарегистрированы. Используйте /start для начала."
                )
                return
            
            # Получаем последнюю сводку
            from datetime import datetime, timedelta
            today = datetime.utcnow().date()
            
            summary = db.query(Summary).filter_by(
                user_id=user.id
            ).filter(
                Summary.date >= datetime.combine(today, datetime.min.time())
            ).order_by(Summary.created_at.desc()).first()
        finally:
            db.close()
        
        if not summary:
            await update.message.reply_text(
                "📭 Сводка за сегодня еще не готова. "
                "Она будет отправлена автоматически после сканирования."
            )
            return
        
        # Форматируем сводку
        summary_text = f"""
📊 Сводка за {summary.date.strftime('%d.%m.%Y')}

{summary.summary_text}

📌 Темы: {', '.join(summary.topics[:5]) if summary.topics else 'Не определены'}
📁 Каналов обработано: {len(summary.channels_included)}
        """
        
        await update.message.reply_text(summary_text)
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверить статус"""
        user_id = update.effective_user.id
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                await update.message.reply_text("❌ Вы не зарегистрированы. Используйте /start")
                return
            
            # Проверяем авторизацию через API (синхронизация с Render)
            auth_status_api = await self._check_auth_from_server(user_id)
            if auth_status_api and auth_status_api.get('authorized'):
                # Синхронизируем статус из удаленной БД
                if not user.is_authorized:
                    user.is_authorized = True
                    user.auth_state = auth_status_api.get('auth_state', 'done')
                    db.commit()
                    logger.info(f"Синхронизирован статус авторизации для пользователя {user_id} в команде /status")
            
            # Проверяем настройки
            channels_count = db.query(Channel).filter_by(user_id=user.id).count()
            active_channels = db.query(Channel).filter_by(user_id=user.id, is_active=True).count()
            
            auth_status = "✅ Авторизован" if user.is_authorized else "❌ Не авторизован"
            bot_status = "🟢 Включен" if user.is_enabled else "🔴 Выключен"
        finally:
            db.close()
        
        status_text = f"""
📊 Статус вашего аккаунта:

{auth_status}
{bot_status}

📁 Всего чатов: {channels_count}
🟢 Активных чатов: {active_channels}

⏰ Время сканирования: {settings.scan_base_hour}:{settings.scan_base_minute:02d} (±{settings.scan_time_variation_minutes} мин)
📊 Максимум чатов за раз: {settings.max_chats_per_scan}

💡 Команды:
/enable - Включить бота
/disable - Выключить бота
/chats - Управление чатами
        """
        
        await update.message.reply_text(status_text)
    
    async def send_summary(self, user_telegram_id: int, summary_text: str):
        """Отправить сводку пользователю"""
        try:
            await self.app.bot.send_message(
                chat_id=user_telegram_id,
                text=f"📊 Ваша ежедневная сводка:\n\n{summary_text}"
            )
            logger.info(f"Сводка отправлена пользователю {user_telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сводки: {e}")
    
    def run(self):
        """Запуск бота (синхронная версия)"""
        logger.info("Запуск Telegram бота...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    async def run_async(self):
        """Запуск бота (асинхронная версия)"""
        logger.info("Запуск Telegram бота (async)...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
        # Ждем бесконечно (бот работает)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("Остановка бота...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
