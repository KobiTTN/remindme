# RemindMe

Веб-додаток для особистих нагадувань через Telegram.

**Стек:** FastAPI · SQLite · APScheduler · Telegram Bot API · Jinja2 · Bootstrap 5

---

## Локальний запуск

```bash
cd remindme

# 1. Створити віртуальне середовище
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Створити .env файл
cp .env.example .env
# Заповни BOT_TOKEN, BOT_USERNAME, SECRET_KEY
# WEBHOOK_URL залиш порожнім для локального запуску

# 4. Запустити
uvicorn app.main:app --reload
```

Відкрий http://localhost:8000

> ⚠️ Для локального тестування Telegram Login Widget потрібен HTTPS домен.
> Скористайся [ngrok](https://ngrok.com): `ngrok http 8000` і вкажи отриманий URL у `WEBHOOK_URL`.

---

## Деплой на Railway

### 1. Підготовка репозиторію

```bash
git init
git add .
git commit -m "Initial commit"
```

### 2. Створення проекту на Railway

1. Зайди на [railway.app](https://railway.app) → **New Project**
2. Обери **Deploy from GitHub repo** → підключи свій репозиторій
3. Railway автоматично знайде `Procfile` і запустить додаток

### 3. Змінні середовища

У Railway → вкладка **Variables** додай:

| Змінна | Значення |
|--------|----------|
| `BOT_TOKEN` | токен від @BotFather |
| `BOT_USERNAME` | @username бота без @ |
| `SECRET_KEY` | довгий випадковий рядок |
| `WEBHOOK_URL` | URL Railway-додатку (напр. `https://remindme-production.up.railway.app`) |

### 4. Перший деплой

Railway автоматично задеплоїть після push у `main`. Перевір логи у вкладці **Deployments**.

### 5. Налаштування Telegram Login Widget

У **@BotFather** виконай команду `/setdomain` і вкажи домен Railway-додатку (без `https://`).

### 6. Перевірка

- Відкрий URL додатку → має з'явитись кнопка "Увійти через Telegram"
- Напиши боту `/start` → бот збереже твій chat_id
- Увійди через сайт → створи нагадування
- Через хвилину перевір чи прийшло повідомлення у Telegram

---

## Структура проекту

```
remindme/
├── app/
│   ├── main.py         # FastAPI, маршрути, планувальник
│   ├── bot.py          # Telegram бот (/start, відправка повідомлень)
│   ├── models.py       # SQLAlchemy моделі (User, Reminder)
│   ├── database.py     # Підключення до SQLite
│   ├── auth.py         # JWT + верифікація Telegram Login Widget
│   └── templates/
│       ├── base.html
│       ├── index.html
│       └── dashboard.html
├── requirements.txt
├── Procfile
├── .env.example
└── README.md
```
