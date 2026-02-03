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
        # Создаем копию, чтобы не изменять оригинал
        data_copy = auth_data.copy()
        
        # Получаем hash из данных
        received_hash = data_copy.pop('hash', '')
        
        if not received_hash:
            logger.warning("Hash отсутствует в данных")
            return False
        
        # Создаем строку для проверки (только те поля, которые есть в данных)
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(data_copy.items()) if k != 'hash')
        
        logger.debug(f"Data check string: {data_check_string}")
        logger.debug(f"Received hash: {received_hash}")
        
        # Вычисляем секретный ключ
        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
        
        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        logger.debug(f"Calculated hash: {calculated_hash}")
        
        # Проверяем подпись
        if calculated_hash != received_hash:
            logger.warning(f"Неверная подпись Telegram. Ожидалось: {calculated_hash}, Получено: {received_hash}")
            return False
        
        # Проверяем время (не старше 24 часов)
        auth_date = int(data_copy.get('auth_date', 0))
        if auth_date == 0:
            logger.warning("auth_date отсутствует")
            return False
            
        if time.time() - auth_date > 86400:
            logger.warning(f"Авторизация устарела. auth_date: {auth_date}, текущее время: {time.time()}")
            return False
        
        logger.info("Подпись проверена успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка проверки подписи: {e}", exc_info=True)
        return False


@app.route('/auth/callback', methods=['POST'])
def auth_callback():
    """Обработка callback от Telegram Login Widget"""
    try:
        data = request.json
        logger.info(f"Получен callback: {data}")
        
        if not data:
            logger.error("Пустые данные в callback")
            return jsonify({'success': False, 'error': 'Пустые данные'}), 400
        
        # Проверяем подпись
        auth_data_copy = data.copy()
        if not verify_telegram_auth(auth_data_copy):
            logger.warning("Неверная подпись Telegram")
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
                logger.info(f"Создание нового пользователя {user_id}")
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
            logger.info(f"Пользователь {user_id} успешно авторизован и сохранен в БД")
            
            # Отправляем уведомление боту о необходимости Client API авторизации
            # (если сессии еще нет)
            session_file = Path(__file__).parent / 'sessions' / f'user_{user.id}.session'
            if not session_file.exists():
                try:
                    import requests
                    bot_token = settings.bot_token
                    message = (
                        "✅ Авторизация через Telegram Login Widget успешна!\n\n"
                        "📱 Для работы с чатами нужна дополнительная авторизация.\n\n"
                        "Используйте команду /setup_client для авторизации через QR-код.\n\n"
                        "💡 Это нужно сделать только **один раз** - сессия сохранится навсегда!"
                    )
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={
                            'chat_id': user_id,
                            'text': message,
                            'parse_mode': 'Markdown'
                        },
                        timeout=10
                    )
                    logger.info(f"Отправлено уведомление пользователю {user_id} о необходимости Client API авторизации")
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
            
            return jsonify({
                'success': True,
                'message': 'Авторизация успешна'
            })
        except Exception as db_error:
            logger.error(f"Ошибка работы с БД: {db_error}", exc_info=True)
            db.rollback()
            return jsonify({'success': False, 'error': f'Ошибка БД: {str(db_error)}'}), 500
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/auth', methods=['GET'])
def auth_page():
    """Страница авторизации"""
    # Пробуем найти index.html (для GitHub Pages) или auth_page.html
    index_path = Path(__file__).parent / 'index.html'
    auth_html_path = Path(__file__).parent / 'auth_page.html'
    
    if index_path.exists():
        return send_from_directory(index_path.parent, 'index.html')
    elif auth_html_path.exists():
        return send_from_directory(auth_html_path.parent, 'auth_page.html')
    else:
        return "Страница авторизации не найдена", 404

@app.route('/', methods=['GET'])
def root():
    """Корневой путь - редирект на страницу авторизации"""
    from flask import redirect
    return redirect('/auth', code=302)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint для Render"""
    return jsonify({'status': 'ok', 'service': 'telegram-summary-bot-auth'}), 200

@app.route('/check-auth/<int:user_id>', methods=['GET'])
def check_auth(user_id):
    """Проверка статуса авторизации пользователя"""
    try:
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if user:
                return jsonify({
                    'authorized': user.is_authorized,
                    'enabled': user.is_enabled,
                    'auth_state': user.auth_state
                }), 200
            else:
                return jsonify({
                    'authorized': False,
                    'enabled': False,
                    'auth_state': None
                }), 200
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Ошибка проверки авторизации: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    logger.info(f"Запуск веб-сервера авторизации на {host}:{port}")
    app.run(host=host, port=port, debug=False)
