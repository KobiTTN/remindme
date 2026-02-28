"""
auth.py — верифікація Telegram Login Widget + JWT сесії в cookies
"""
import hashlib
import hmac
import os
import time

from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from fastapi import Cookie, HTTPException, status

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM  = "HS256"
TOKEN_TTL_DAYS = 7


# ── Telegram Login Widget ──────────────────────────────────────────────────────

def verify_telegram_auth(data: dict) -> bool:
    """
    Перевіряє підпис даних від Telegram Login Widget.
    Алгоритм: HMAC-SHA256 з ключем = SHA256(BOT_TOKEN).
    Докладніше: https://core.telegram.org/widgets/login#checking-authorization
    """
    bot_token = os.getenv("BOT_TOKEN", "")
    received_hash = data.get("hash", "")

    # Формуємо рядок для перевірки (всі поля крім hash, відсортовані)
    check_fields = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_fields.items()))

    # Секретний ключ = SHA256 від токена бота
    secret_key = hashlib.sha256(bot_token.encode()).digest()

    # Очікуваний хеш
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # Перевірка часу: дані не старіші 24 годин
    auth_date = int(data.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        return False

    return hmac.compare_digest(received_hash, expected_hash)


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_session_token(user_id: int, telegram_id: int, first_name: str) -> str:
    """Створює JWT токен для сесії користувача"""
    payload = {
        "sub":         str(user_id),
        "telegram_id": telegram_id,
        "first_name":  first_name,
        "exp":         datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_session_token(token: str) -> dict:
    """Декодує JWT токен. Викидає JWTError якщо токен недійсний або прострочений."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── FastAPI Dependency ─────────────────────────────────────────────────────────

def get_current_user(session: str = Cookie(default=None)) -> dict:
    """
    FastAPI dependency — витягує поточного користувача з cookie.
    Викидає 401 якщо cookie відсутня або токен недійсний.
    """
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_session_token(session)
        return {
            "user_id":    int(payload["sub"]),
            "telegram_id": payload["telegram_id"],
            "first_name":  payload.get("first_name", ""),
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
