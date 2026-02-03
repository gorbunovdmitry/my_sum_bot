#!/usr/bin/env python3
"""
Скрипт для ручной авторизации через Telethon
Используйте этот скрипт, если код не приходит через бота
"""
import asyncio
from telethon import TelegramClient
from config import settings
from pathlib import Path

async def manual_auth():
    phone = input("Введите номер телефона (+79001234567): ").strip()
    
    # Создаем сессию
    session_file = "manual_auth.session"
    client = TelegramClient(session_file, settings.telegram_api_id, settings.telegram_api_hash)
    
    try:
        await client.start(phone=phone)
        print("✅ Авторизация успешна!")
        
        me = await client.get_me()
        print(f"Пользователь: {me.first_name} {me.phone}")
        
        # Копируем сессию в нужное место
        user_id = input("Введите ваш Telegram ID (можно узнать у @userinfobot): ").strip()
        target_session = Path("sessions") / f"user_{user_id}.session"
        
        import shutil
        Path("sessions").mkdir(exist_ok=True)
        shutil.copy(session_file, target_session)
        print(f"✅ Сессия сохранена в {target_session}")
        print("Теперь используйте /auth в боте - он должен найти сессию!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(manual_auth())
