"""
Веб-сервер для обработки авторизации через Telegram Login Widget
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from loguru import logger
import hashlib
import hmac
import time
import requests
from pathlib import Path
from config import settings
from database import User, SessionLocal

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для работы с Telegram Widget

# Секретный ключ для проверки подписи (из Bot Token)
BOT_TOKEN = settings.bot_token


def verify_telegram_auth(auth_data):
    """Проверка подписи от Telegram"""
    try:
        # Получаем hash из данных
        received_hash = auth_data.pop('hash', '')
        
        # Создаем строку для проверки
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(auth_data.items()))
        
        # Вычисляем секретный ключ
        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
        
        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Проверяем подпись
        if calculated_hash != received_hash:
            logger.warning("Неверная подпись Telegram")
            return False
        
        # Проверяем время (не старше 24 часов)
        auth_date = int(auth_data.get('auth_date', 0))
        if time.time() - auth_date > 86400:
            logger.warning("Авторизация устарела")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Ошибка проверки подписи: {e}")
        return False


@app.route('/auth/callback', methods=['POST'])
def auth_callback():
    """Обработка callback от Telegram Login Widget"""
    try:
        data = request.json
        
        # Проверяем подпись
        if not verify_telegram_auth(data.copy()):
            return jsonify({'success': False, 'error': 'Неверная подпись'}), 400
        
        user_id = data.get('id')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        username = data.get('username', '')
        
        logger.info(f"Авторизация пользователя {user_id} ({first_name} {last_name})")
        
        # Сохраняем в БД
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            
            if not user:
                user = User(telegram_id=user_id)
                db.add(user)
            
            # Обновляем данные пользователя
            user.is_authorized = True
            user.auth_state = 'done'
            # Сохраняем имя пользователя в preferences
            if not user.preferences:
                user.preferences = {}
            user.preferences['first_name'] = first_name
            user.preferences['last_name'] = last_name
            user.preferences['username'] = username
            
            db.commit()
            logger.info(f"Пользователь {user_id} успешно авторизован")
            
            return jsonify({
                'success': True,
                'message': 'Авторизация успешна'
            })
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/auth', methods=['GET'])
def auth_page():
    """Страница авторизации"""
    auth_html_path = Path(__file__).parent / 'auth_page.html'
    if auth_html_path.exists():
        return send_from_directory(auth_html_path.parent, 'auth_page.html')
    else:
        return "Страница авторизации не найдена", 404


if __name__ == '__main__':
    logger.info("Запуск веб-сервера авторизации на http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
