import os
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# We send simple HTTP requests via python-telegram-bot in telegram_bot.py.
# Here we only build deep-link URLs that open the Streamlit case page.
def build_case_link(case_id: int) -> str:
    # Assuming Streamlit is served at same origin; replace with your public URL.
    base = os.getenv("PUBLIC_APP_URL", "http://localhost:8501")
    return f"{base}/?case_id={case_id}"
