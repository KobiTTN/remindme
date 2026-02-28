"""
database.py — підключення до SQLite через SQLAlchemy
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# URL бази даних (за замовчуванням SQLite у файлі remindme.db)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./remindme.db")

# check_same_thread=False дозволяє використовувати з'єднання з кількох потоків (потрібно для APScheduler)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Фабрика сесій
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовий клас для моделей
Base = declarative_base()


def get_db():
    """Dependency для FastAPI — відкриває і закриває сесію після запиту"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
