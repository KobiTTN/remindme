"""
main.py — FastAPI додаток: маршрути, планувальник, webhook
"""
import os
import logging
import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from telegram import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import engine, SessionLocal, get_db
from app.models import Base, User, Reminder
from app.auth import verify_telegram_auth, create_session_token, get_current_user
from app.bot import build_application, send_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Налаштування ───────────────────────────────────────────────────────────────

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")       # напр. https://your-app.railway.app
BOT_USERNAME = os.getenv("BOT_USERNAME", "")     # @username бота без @

templates = Jinja2Templates(directory="app/templates")

# Telegram Application (для webhook)
tg_app = build_application()

# Планувальник
scheduler = AsyncIOScheduler()


# ── Планувальник нагадувань ────────────────────────────────────────────────────

async def check_and_send_reminders():
    """
    Запускається кожну хвилину.
    Знаходить прострочені нагадування і відправляє їх у Telegram.
    """
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        due = db.query(Reminder).filter(
            Reminder.remind_at <= now,
            Reminder.is_sent == False
        ).all()

        logger.info(f"Scheduler tick: now={now.strftime('%H:%M:%S')} UTC, due={len(due)}")

        for reminder in due:
            user = db.query(User).filter(User.id == reminder.user_id).first()
            if not user:
                logger.error(f"User not found for reminder {reminder.id} (user_id={reminder.user_id})")
                continue
            text = f"⏰ Нагадування:\n\n{reminder.text}"
            logger.info(f"Sending reminder {reminder.id} to telegram_id={user.telegram_id}")
            ok = await send_message(user.telegram_id, text)
            if ok:
                reminder.is_sent = True
                db.commit()
                logger.info(f"Sent reminder {reminder.id} to user {user.telegram_id}")
            else:
                logger.error(f"Failed to send reminder {reminder.id} to {user.telegram_id}")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
    finally:
        db.close()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)       # створюємо таблиці якщо не існують
    logger.info("Database tables created")

    await tg_app.initialize()                   # ініціалізуємо Telegram Application

    if WEBHOOK_URL:
        webhook_path = f"{WEBHOOK_URL}/webhook"
        await tg_app.bot.set_webhook(url=webhook_path)
        logger.info(f"Webhook set: {webhook_path}")
    else:
        logger.warning("WEBHOOK_URL not set — webhook not configured")

    scheduler.add_job(check_and_send_reminders, "interval", minutes=1, id="reminders")
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown()
    await tg_app.shutdown()


app = FastAPI(title="RemindMe", lifespan=lifespan)


# ── Маршрути ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Головна сторінка: якщо авторизований — редирект на dashboard"""
    session = request.cookies.get("session")
    if session:
        try:
            from app.auth import decode_session_token
            decode_session_token(session)
            return RedirectResponse("/dashboard")
        except Exception:
            pass
    return templates.TemplateResponse("index.html", {
        "request": request,
        "bot_username": BOT_USERNAME,
    })


@app.get("/auth/telegram")
async def auth_telegram(request: Request):
    """
    Callback від Telegram Login Widget.
    Telegram надсилає user data як query params + hash для верифікації.
    """
    data = dict(request.query_params)

    if not verify_telegram_auth(data):
        raise HTTPException(status_code=400, detail="Invalid Telegram auth data")

    telegram_id = int(data["id"])
    first_name  = data.get("first_name", "")
    username    = data.get("username", None)

    # Зберігаємо або оновлюємо користувача
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.username   = username
            user.first_name = first_name
            db.commit()

        token = create_session_token(user.id, user.telegram_id, user.first_name)
    finally:
        db.close()

    # Встановлюємо JWT у httponly cookie
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,       # недоступна через JS
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 днів
    )
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: dict = Depends(get_current_user)):
    """Список нагадувань + форма створення нового"""
    db = SessionLocal()
    try:
        reminders = db.query(Reminder).filter(
            Reminder.user_id == current_user["user_id"]
        ).order_by(Reminder.remind_at).all()
    finally:
        db.close()

    upcoming = [r for r in reminders if not r.is_sent]
    history  = [r for r in reminders if r.is_sent]

    return templates.TemplateResponse("dashboard.html", {
        "request":      request,
        "user":         current_user,
        "upcoming":     upcoming,
        "history":      history,
    })


@app.post("/reminders")
async def create_reminder(
    text:      str = Form(...),
    remind_at: str = Form(...),          # "2026-03-01T14:30"
    current_user: dict = Depends(get_current_user),
):
    """Створення нового нагадування"""
    try:
        remind_dt = datetime.datetime.fromisoformat(remind_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    if remind_dt <= datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Date must be in the future")

    db = SessionLocal()
    try:
        reminder = Reminder(
            user_id=current_user["user_id"],
            text=text.strip(),
            remind_at=remind_dt,
        )
        db.add(reminder)
        db.commit()
    finally:
        db.close()

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/reminders/{reminder_id}/delete")
async def delete_reminder(
    reminder_id:  int,
    current_user: dict = Depends(get_current_user),
):
    """Видалення нагадування (тільки власне)"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(
            Reminder.id == reminder_id,
            Reminder.user_id == current_user["user_id"],
        ).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        db.delete(reminder)
        db.commit()
    finally:
        db.close()

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/logout")
async def logout():
    """Видалення сесії"""
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session")
    return response


@app.post("/webhook")
async def webhook(request: Request):
    """Приймає оновлення від Telegram (webhook mode)"""
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
