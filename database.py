"""
Модели базы данных для хранения сообщений и метаданных
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import settings

Base = declarative_base()


class User(Base):
    """Пользователь бота"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    session_data_encrypted = Column(Text, nullable=True)  # Зашифрованная сессия
    preferences = Column(JSON, default={})  # Настройки пользователя
    is_authorized = Column(Boolean, default=False)  # Авторизован ли через Client API
    is_enabled = Column(Boolean, default=False)  # Включен ли бот для пользователя
    auth_state = Column(String, nullable=True)  # Состояние авторизации: 'phone', 'code', 'done'
    pending_phone = Column(String, nullable=True)  # Телефон в процессе авторизации
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    channels = relationship("Channel", back_populates="user")
    summaries = relationship("Summary", back_populates="user")


class Channel(Base):
    """Канал/чат для сканирования"""
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_chat_id = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=True)
    chat_type = Column(String, nullable=False)  # 'private', 'group', 'channel', 'supergroup'
    priority = Column(Integer, default=1)  # 1-высокий, 2-средний, 3-низкий
    is_active = Column(Boolean, default=True)
    last_scan_time = Column(DateTime, nullable=True)  # Время последнего сканирования
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="channels")
    messages = relationship("Message", back_populates="channel")


class Message(Base):
    """Сообщение из чата"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    telegram_message_id = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    message_type = Column(String, default="text")  # 'text', 'media', 'link', etc.
    importance_score = Column(Float, default=0.0)  # Оценка важности (0-1)
    processed_at = Column(DateTime, nullable=True)
    
    # Связи
    channel = relationship("Channel", back_populates="messages")


class Summary(Base):
    """Сводка для пользователя"""
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    topics = Column(JSON, default=[])  # Список тем
    channels_included = Column(JSON, default=[])  # ID каналов в сводке
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="summaries")


class UserInterest(Base):
    """Интересы пользователя"""
    __tablename__ = "user_interests"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    keyword = Column(String, nullable=False, index=True)
    weight = Column(Float, default=1.0)  # Вес интереса (0-1)
    source = Column(String, default="manual")  # 'manual', 'auto', 'interaction'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Создаем движок БД
engine = create_engine(
    settings.database_url,
    echo=False,  # Установите True для отладки SQL
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Создаем таблицы
Base.metadata.create_all(engine)

# Создаем сессию
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Получить сессию БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
