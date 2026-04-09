import asyncio
import logging

from telegram.ext import ApplicationBuilder

from config import BOT_TOKEN
from database import init_db
from handlers import register_handlers
import scheduler as sched

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def on_startup(app):
    logger.info("Инициализация базы данных...")
    await init_db()

    logger.info("Загрузка напоминаний...")
    await sched.load_all_reminders()

    sched.set_app(app)
    sched.scheduler.start()
    logger.info("Планировщик запущен.")


async def on_shutdown(app):
    sched.scheduler.shutdown(wait=False)
    logger.info("Планировщик остановлен.")


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    register_handlers(app)

    logger.info("Бот запускается...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
