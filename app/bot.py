"""
bot.py — Telegram бот: обробка /start і відправка повідомлень
"""
import os
import logging

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.database import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


# ── /start handler ─────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробляє команду /start.
    Зберігає або оновлює користувача в БД.
    """
    tg_user = update.effective_user
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            # Новий користувач — зберігаємо
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
            )
            db.add(user)
            db.commit()
            logger.info(f"New user registered: {tg_user.id} (@{tg_user.username})")

        await update.message.reply_text(
            f"👋 Привіт, {tg_user.first_name}!\n\n"
            "Я буду нагадувати тобі про важливі речі.\n"
            "Відкрий веб-сайт, щоб створити нагадування."
        )
    finally:
        db.close()


# ── Application (webhook mode) ─────────────────────────────────────────────────

def build_application() -> Application:
    """Створює та налаштовує Telegram Application"""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    return app


# ── Відправка повідомлення через Bot API ───────────────────────────────────────

async def send_message(chat_id: int, text: str) -> bool:
    """
    Відправляє повідомлення користувачу через Telegram Bot API.
    Повертає True якщо успішно.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False
