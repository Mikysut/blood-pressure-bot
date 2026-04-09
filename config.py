import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "data/blood_pressure.db")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан. Создайте файл .env с BOT_TOKEN=...")
