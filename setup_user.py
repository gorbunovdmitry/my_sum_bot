"""
Скрипт для первоначальной настройки пользователя
Авторизация через Telegram Client API и выбор чатов
"""
import asyncio
from telethon import TelegramClient
from loguru import logger
from config import settings
from database import User, Channel, SessionLocal


async def setup_user():
    """Настройка нового пользователя"""
    
    print("=" * 50)
    print("Настройка Telegram Summary Bot")
    print("=" * 50)
    
    # Запрашиваем данные пользователя
    phone = input("\nВведите ваш номер телефона (с кодом страны, например +79991234567): ")
    
    # Создаем клиент
    session_file = settings.session_dir / f"setup_{phone.replace('+', '')}.session"
    client = TelegramClient(
        str(session_file),
        settings.telegram_api_id,
        settings.telegram_api_hash
    )
    
    try:
        await client.start(phone=phone)
        print("\n✅ Успешная авторизация!")
        
        # Получаем информацию о пользователе
        me = await client.get_me()
        print(f"\nПользователь: {me.first_name} {me.last_name or ''}")
        print(f"Telegram ID: {me.id}")
        print(f"Username: @{me.username or 'не указан'}")
        
        # Получаем список диалогов
        print("\nЗагрузка списка чатов...")
        dialogs = await client.get_dialogs()
        
        print(f"\nНайдено {len(dialogs)} чатов/каналов")
        print("\nСписок чатов:")
        print("-" * 50)
        
        chat_list = []
        for i, dialog in enumerate(dialogs, 1):
            entity = dialog.entity
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            chat_type = 'private' if hasattr(entity, 'first_name') else 'channel' if hasattr(entity, 'username') else 'group'
            
            chat_list.append({
                'id': entity.id,
                'title': title,
                'type': chat_type,
                'unread': dialog.unread_count
            })
            
            print(f"{i:3d}. [{chat_type:10s}] {title[:40]:40s} (непрочитано: {dialog.unread_count})")
        
        # Выбор чатов для сканирования
        print("\n" + "=" * 50)
        print("Выберите чаты для сканирования:")
        print("Введите номера через запятую (например: 1,3,5-10,15)")
        print("Или 'all' для выбора всех")
        print("Или 'skip' чтобы пропустить (можно настроить позже)")
        
        selection = input("\nВаш выбор: ").strip().lower()
        
        selected_chats = []
        if selection == 'all':
            selected_chats = chat_list
        elif selection != 'skip':
            # Парсим выбор
            indices = []
            for part in selection.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    indices.extend(range(start - 1, end))
                else:
                    indices.append(int(part) - 1)
            
            selected_chats = [chat_list[i] for i in indices if 0 <= i < len(chat_list)]
        
        # Сохраняем в БД
        db = SessionLocal()
        try:
            # Создаем или обновляем пользователя
            user = db.query(User).filter_by(telegram_id=me.id).first()
            if not user:
                user = User(telegram_id=me.id, phone=phone)
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                user.phone = phone
                db.commit()
            
            # Сохраняем выбранные чаты
            if selected_chats:
                print(f"\nСохранение {len(selected_chats)} чатов...")
                
                for chat_info in selected_chats:
                    channel = db.query(Channel).filter_by(
                        telegram_chat_id=chat_info['id'],
                        user_id=user.id
                    ).first()
                    
                    if not channel:
                        channel = Channel(
                            user_id=user.id,
                            telegram_chat_id=chat_info['id'],
                            title=chat_info['title'],
                            chat_type=chat_info['type'],
                            priority=1,
                            is_active=True
                        )
                        db.add(channel)
                
                db.commit()
                print("✅ Чаты сохранены!")
            else:
                print("\n⚠️ Чаты не выбраны. Вы можете настроить их позже.")
        finally:
            db.close()
        
        print("\n" + "=" * 50)
        print("✅ Настройка завершена!")
        print(f"\nВаш Telegram ID: {me.id}")
        print("Используйте этот ID для связи с ботом.")
        print("\nТеперь вы можете запустить основной бот командой:")
        print("python main.py")
        
    except Exception as e:
        logger.error(f"Ошибка настройки: {e}")
        print(f"\n❌ Ошибка: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    logger.add("logs/setup.log", rotation="1 day")
    asyncio.run(setup_user())
