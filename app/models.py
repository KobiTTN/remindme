"""
models.py — SQLAlchemy моделі: User і Reminder
"""
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """Користувач, авторизований через Telegram"""
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False)  # chat_id від Telegram
    username    = Column(String, nullable=True)                 # @username (може бути відсутній)
    first_name  = Column(String, nullable=True)
    created_at  = Column(DateTime, default=datetime.datetime.utcnow)

    reminders = relationship("Reminder", back_populates="user", lazy="dynamic")


class Reminder(Base):
    """Нагадування користувача"""
    __tablename__ = "reminders"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    text       = Column(String, nullable=False)
    remind_at  = Column(DateTime, nullable=False)   # коли відправити
    is_sent    = Column(Boolean, default=False)      # відправлено? (не видаляємо — зберігаємо історію)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="reminders")
