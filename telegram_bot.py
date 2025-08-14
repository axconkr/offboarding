# telegram_bot.py - python-telegram-bot v20 compatible, ASCII-only
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from db import SessionLocal, User  # SQLAlchemy session/model

# Logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("offboarding.bot")

# Load .env from script directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

def find_user_by_chat_id(chat_id: int) -> Optional[User]:
    with SessionLocal() as db:
        return db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Hello! Link your account by sending:\n\n/start your_email@example.com"
        )
        return

    email = args[0].strip().lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            await update.effective_message.reply_text(
                f"Email not found: {email}"
            )
            return
        user.telegram_chat_id = str(chat_id)
        db.commit()

    await update.effective_message.reply_text(
        f"Linked successfully.\nemail={email}\nchat_id={chat_id}"
    )
    log.info("Linked %s -> chat_id=%s", email, chat_id)

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = find_user_by_chat_id(chat_id)
    if not user:
        await update.effective_message.reply_text(
            "Not linked yet. Use /start your_email@example.com"
        )
        return
    role = getattr(user.role, "value", str(user.role))
    await update.effective_message.reply_text(
        f"name={user.name}\nemail={user.email}\nrole={role}\nchat_id={chat_id}"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("pong")

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("ping", ping))
    log.info("Starting bot...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
