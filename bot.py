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
        self.app.add_handler(CommandHandler("import_session", self.import_session))
        
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
        """Начать процесс авторизации через номер телефона (удобно для мобильных)"""
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
            
            # Проверяем, есть ли уже сессия
            session_file = settings.session_dir / f"user_{user.id}.session"
            if session_file.exists() and user.phone:
                # Пробуем подключиться
                client = SafeTelegramClient(user.id, user.phone)
                if await client.connect():
                    user.is_authorized = True
                    user.auth_state = 'done'
                    db.commit()
                    await update.message.reply_text(
                        "✅ Вы уже авторизованы!\n"
                        "Используйте /enable чтобы включить бота."
                    )
                    # Сохраняем клиент в app_instance
                    if self.app_instance:
                        self.app_instance.telegram_clients[user.id] = client
                    return
            
            # Предлагаем варианты авторизации
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [InlineKeyboardButton("📱 Через номер телефона", callback_data="auth_method_phone")],
                [InlineKeyboardButton("💻 Использовать Telegram Desktop", callback_data="auth_method_desktop")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔐 Выберите способ авторизации:\n\n"
                "📱 **Через номер телефона** - стандартный способ\n"
                "💻 **Telegram Desktop** - если код не приходит\n\n"
                "💡 Рекомендуем Telegram Desktop, если код не приходит",
                reply_markup=reply_markup
            )
            
            logger.info(f"Пользователь {user_id} начал авторизацию, ожидается выбор метода")
            
        except Exception as e:
            logger.error(f"Ошибка в команде /auth: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Произошла ошибка: {e}\n\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        finally:
            db.close()
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (для авторизации через телефон)"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Игнорируем команды
        if text.startswith('/'):
            return
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user or not user.auth_state:
                # Игнорируем сообщения, если пользователь не в процессе авторизации
                return
            
            # Обработка номера телефона
            if user.auth_state == 'phone':
                phone = text.strip()

                # Проверяем формат номера
                if not phone.startswith('+'):
                    await update.message.reply_text(
                        "❌ Номер должен быть в международном формате и начинаться с '+'.\n"
                        "Например: +79001234567\n\n"
                        "Попробуйте еще раз:"
                    )
                    return

                # Сохраняем телефон и запрашиваем код
                user.pending_phone = phone
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
                    
                    logger.info(f"Отправка запроса кода для номера {phone}")
                    
                    # Пробуем использовать start() напрямую - он может работать лучше
                    # start() автоматически запросит код и будет ждать его
                    # Но нам нужно получить код от пользователя, поэтому используем send_code_request
                    result = await temp_client.send_code_request(phone)
                    
                    logger.info(f"Результат send_code_request: type={type(result)}, phone_code_hash={getattr(result, 'phone_code_hash', 'N/A')}")
                    
                    # Сохраняем phone_code_hash для дальнейшего использования
                    if not hasattr(self, 'phone_code_hashes'):
                        self.phone_code_hashes = {}
                    if hasattr(result, 'phone_code_hash'):
                        self.phone_code_hashes[user_id] = result.phone_code_hash
                        logger.info(f"Сохранен phone_code_hash для user={user_id}")
                    
                    # Определяем тип отправки кода
                    code_type = "Telegram сообщение"
                    code_length = 5
                    where_to_find = "В Telegram, в чате **Telegram** (\"Login code\")"
                    
                    if hasattr(result, 'type'):
                        type_name = str(result.type)
                        logger.info(f"Тип отправки кода: {type_name}")
                        
                        if 'Sms' in type_name or result.type.CONSTRUCTOR_ID == 0x3cbbcd6c:
                            code_type = "SMS"
                            where_to_find = "В SMS на номер телефона"
                        elif 'Call' in type_name:
                            code_type = "телефонный звонок"
                            where_to_find = "В телефонном звонке (автоответчик)"
                        elif 'FlashCall' in type_name:
                            code_type = "мгновенный звонок"
                            where_to_find = "В номере входящего звонка"
                        elif 'App' in type_name:
                            code_type = "Telegram приложение"
                            where_to_find = "В Telegram, в чате **Telegram** (\"Login code\")"
                            if hasattr(result.type, 'length'):
                                code_length = result.type.length
                    
                    logger.info(f"Тип отправки: {code_type}, длина кода: {code_length}, где искать: {where_to_find}")
                    
                    # Сохраняем клиент для дальнейшего использования
                    if not hasattr(self, 'auth_clients'):
                        self.auth_clients = {}
                    self.auth_clients[user_id] = temp_client
                    
                    await update.message.reply_text(
                        f"✅ Запрос кода отправлен!\n\n"
                        f"📱 Тип отправки: **{code_type}**\n"
                        f"🔢 Длина кода: **{code_length}** цифр\n\n"
                        f"📍 **Где искать код:**\n"
                        f"{where_to_find}\n\n"
                        "💡 **Важно:**\n"
                        "• Откройте Telegram на телефоне\n"
                        "• Найдите чат с названием **\"Telegram\"** (синий значок)\n"
                        "• Код придет как сообщение \"Login code: XXXXX\"\n"
                        "• Иногда приходит пуш-уведомлением\n\n"
                        "⏳ Код обычно приходит в течение 10-60 секунд.\n\n"
                        f"Отправьте сюда код из {code_length} цифр (например: {'1' * code_length})."
                    )
                    logger.info(f"send_code_request успешно выполнен для user={user_id} phone={phone} type={code_type}")
                except Exception as e:
                    logger.error(f"Ошибка запроса кода: {e}", exc_info=True)
                    err = str(e)
                    if "FLOOD_WAIT" in err:
                        await update.message.reply_text(
                            "⏳ Telegram временно ограничил запросы кода (FLOOD_WAIT).\n"
                            "Подождите 2–5 минут и попробуйте снова: /auth"
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Ошибка: {e}\n\n"
                            "Попробуйте еще раз: /auth"
                        )
                    user.auth_state = None
                    user.pending_phone = None
                    db.commit()
                    # Закрываем клиент при ошибке
                    if user_id in self.auth_clients:
                        try:
                            await self.auth_clients[user_id].disconnect()
                        except:
                            pass
                        del self.auth_clients[user_id]
            
            # Обработка кода
            elif user.auth_state == 'code':
                code = text.strip()
                
                # Проверяем, что код состоит из цифр
                if not code.isdigit():
                    await update.message.reply_text(
                        "❌ Код должен состоять только из цифр\n"
                        "Попробуйте еще раз:"
                    )
                    return
                
                try:
                    temp_client = self.auth_clients.get(user_id) if hasattr(self, 'auth_clients') else None
                    if not temp_client:
                        await update.message.reply_text(
                            "❌ Сессия авторизации истекла. Попробуйте /auth еще раз"
                        )
                        user.auth_state = None
                        db.commit()
                        return
                    
                    # Авторизуемся (с небольшой задержкой для безопасности)
                    await asyncio.sleep(0.5)  # Задержка для снижения риска блокировки
                    
                    # Используем phone_code_hash если он был сохранен
                    phone_code_hash = None
                    if hasattr(self, 'phone_code_hashes') and user_id in self.phone_code_hashes:
                        phone_code_hash = self.phone_code_hashes[user_id]
                        logger.info(f"Использование сохраненного phone_code_hash для user={user_id}")
                    
                    if phone_code_hash:
                        await temp_client.sign_in(user.pending_phone, code, phone_code_hash=phone_code_hash)
                    else:
                        await temp_client.sign_in(user.pending_phone, code)
                    
                    # Получаем информацию о пользователе
                    me = await temp_client.get_me()
                    
                    # Сохраняем сессию в правильное место
                    import shutil
                    temp_session = settings.session_dir / f"temp_auth_{user_id}.session"
                    final_session = settings.session_dir / f"user_{user.id}.session"
                    if temp_session.exists():
                        shutil.copy(temp_session, final_session)
                    
                    # Сохраняем успешную авторизацию
                    user.phone = me.phone or user.pending_phone
                    user.is_authorized = True
                    user.auth_state = 'done'
                    user.pending_phone = None
                    db.commit()
                    
                    # Закрываем временный клиент
                    await temp_client.disconnect()
                    if hasattr(self, 'auth_clients'):
                        self.auth_clients.pop(user_id, None)
                    
                    # Удаляем временную сессию
                    if temp_session.exists():
                        temp_session.unlink()
                    
                    # Сохраняем клиент в app_instance
                    if self.app_instance:
                        safe_client = SafeTelegramClient(user.id, user.phone)
                        if await safe_client.connect():
                            self.app_instance.telegram_clients[user.id] = safe_client
                    
                    await update.message.reply_text(
                        "✅ Авторизация успешна!\n\n"
                        "Теперь вы можете:\n"
                        "• /enable - Включить бота\n"
                        "• /chats - Выбрать чаты для сканирования\n\n"
                        "💡 Сессия сохранена - больше не нужно авторизовываться!"
                    )
                    logger.info(f"Пользователь {user_id} успешно авторизован")
                except Exception as e:
                    logger.error(f"Ошибка авторизации: {e}", exc_info=True)
                    error_msg = str(e)
                    if "PHONE_CODE_INVALID" in error_msg:
                        await update.message.reply_text(
                            "❌ Неверный код. Попробуйте еще раз:\n"
                            "Отправьте код, который вы получили в Telegram"
                        )
                    elif "PHONE_NUMBER_UNOCCUPIED" in error_msg:
                        await update.message.reply_text(
                            "❌ Этот номер телефона не зарегистрирован в Telegram.\n"
                            "Попробуйте другой номер: /auth"
                        )
                        user.auth_state = None
                        user.pending_phone = None
                        db.commit()
                    else:
                        await update.message.reply_text(
                            f"❌ Ошибка авторизации: {e}\n\n"
                            "Попробуйте еще раз: /auth"
                        )
                        user.auth_state = None
                        user.pending_phone = None
                        db.commit()
                    
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
                    # Проверяем, есть ли сессия
                    session_file = settings.session_dir / f"user_{user.id}.session"
                    if not session_file.exists() or not user.phone:
                        await update.message.reply_text(
                            "⚠️ Для работы с чатами нужна авторизация через Telegram Client API.\n\n"
                            "Используйте команду /auth для авторизации через номер телефона."
                        )
                        return
                    
                    # Создаем клиент если его нет
                    client = SafeTelegramClient(user.id, user.phone)
                    if await client.connect():
                        self.app_instance.telegram_clients[user.id] = client
                    else:
                        await update.message.reply_text(
                            "❌ Не удалось подключиться к Telegram Client API.\n\n"
                            "Возможные причины:\n"
                            "• Сессия устарела\n"
                            "• Нужна повторная авторизация\n\n"
                            "Используйте /auth для повторной авторизации."
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
