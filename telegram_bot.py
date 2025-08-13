import os, logging, re
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from db import SessionLocal, User
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")

def _token_error(token: str) -> str | None:
    if not token:
        return "환경변수 TELEGRAM_BOT_TOKEN 이 비어 있습니다."
    if not re.match(r"^\d{8,10}:[A-Za-z0-9_-]{35,}$", token):
        return "텔레그램 토큰 형식이 올바르지 않습니다. @BotFather 에서 새 토큰을 받아 .env에 넣어주세요."
    return None

err = _token_error(BOT_TOKEN)
if err:
    raise SystemExit(f"[Bot init error] {err}")

HELP_TEXT = (
    "안녕하세요! 오프보딩 알림 봇입니다.\n"
    "/start - 시작 및 계정 연결 (예: /start hr@example.com)\n"
    "/whoami - 내 계정 확인\n"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        await update.message.reply_text("이메일을 함께 입력해주세요. 예) /start hr@example.com")
        return
    email = args[0].strip().lower()

    db: Session = SessionLocal()
    user = db.query(User).filter(User.email==email).first()
    if not user:
        await update.message.reply_text("해당 이메일 사용자가 없습니다. 관리자에게 문의하세요.")
        return
    user.telegram_chat_id = str(chat_id)
    db.add(user)
    db.commit()
    await update.message.reply_text("연결되었습니다! 이제 알림을 받을 수 있습니다.")

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    db: Session = SessionLocal()
    user = db.query(User).filter(User.telegram_chat_id==chat_id).first()
    if not user:
        await update.message.reply_text("계정이 연결되지 않았습니다. /start 이메일 로 연결하세요.")
        return
    await update.message.reply_text(f"{user.name} / {user.email} / {user.role.value}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.run_polling()

if __name__ == "__main__":
    main()
