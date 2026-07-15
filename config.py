import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_IDS = {
    int(item.strip())
    for item in os.getenv("ADMIN_CHAT_IDS", "").split(",")
    if item.strip().isdigit()
}
OWNER_USER_IDS = {
    int(item.strip())
    for item in os.getenv("OWNER_USER_IDS", "").split(",")
    if item.strip().isdigit()
}

DATABASE_PATH = BASE_DIR / "data" / "passwords.db"
LOG_PATH = BASE_DIR / "logs" / "bot.log"
DELETE_NOTICE_AFTER_SECONDS = int(
    os.getenv("DELETE_NOTICE_AFTER_SECONDS", "10")
)

if not BOT_TOKEN:
    raise RuntimeError("Chưa cấu hình BOT_TOKEN trong file .env")
