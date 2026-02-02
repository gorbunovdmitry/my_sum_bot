"""
Конфигурация бота для безопасного сканирования Telegram чатов
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram API
    telegram_api_id: int
    telegram_api_hash: str
    bot_token: str
    
    # База данных
    database_url: str = "sqlite:///./data/summary_bot.db"
    
    # Redis (опционально)
    redis_url: Optional[str] = None
    
    # AI/ML
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    local_model_path: Optional[str] = None
    
    # Масштабирование и производительность
    max_workers: int = 4  # Количество параллельных потоков для обработки
    enable_caching: bool = True  # Включить кэширование результатов
    cache_ttl_seconds: int = 3600  # Время жизни кэша (1 час)
    batch_size: int = 4  # Размер батча для обработки
    use_mps: bool = True  # Использовать Metal Performance Shaders на Mac
    
    # Настройки сканирования (безопасные по умолчанию)
    scan_base_hour: int = 22
    scan_base_minute: int = 0
    scan_time_variation_minutes: int = 30  # ±30 минут
    max_chats_per_scan: int = 50
    scan_delay_min_seconds: float = 1.0
    scan_delay_max_seconds: float = 5.0
    
    # Безопасность
    skip_scan_probability: float = 0.05  # 5% вероятность пропустить
    max_requests_per_second: int = 20  # Запас от лимита
    
    # Логирование
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"
    
    # Пути
    session_dir: Path = Path("./sessions")
    data_dir: Path = Path("./data")
    
    # Веб-сервер авторизации
    auth_server_url: Optional[str] = None  # Если None, используется localhost:5000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Создаем директории если их нет
settings = Settings()
settings.session_dir.mkdir(exist_ok=True)
settings.data_dir.mkdir(exist_ok=True)
Path(settings.log_file).parent.mkdir(exist_ok=True)
