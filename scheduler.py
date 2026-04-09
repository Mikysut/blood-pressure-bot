import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import TIMEZONE
import database

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=TIMEZONE)
_bot_app = None


def set_app(app):
    global _bot_app
    _bot_app = app


async def _send_reminder(user_id: int):
    if _bot_app is None:
        return
    try:
        await _bot_app.bot.send_message(
            chat_id=user_id,
            text=(
                "Время замерить давление!\n\n"
                "Отправь показания в формате:\n"
                "<code>120/80 72</code>  (давление пульс)\n"
                "или просто  <code>120/80</code>"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Не удалось отправить напоминание пользователю %s: %s", user_id, e)


def _job_id(user_id: int, slot: str) -> str:
    return f"remind_{user_id}_{slot}"


def schedule_user(user_id: int, morning: str, evening: str):
    tz = pytz.timezone(TIMEZONE)

    for slot, time_str in (("morning", morning), ("evening", evening)):
        job_id = _job_id(user_id, slot)
        hour, minute = map(int, time_str.split(":"))

        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            _send_reminder,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id=job_id,
            args=[user_id],
            replace_existing=True,
        )


def unschedule_user(user_id: int):
    for slot in ("morning", "evening"):
        job_id = _job_id(user_id, slot)
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)


async def load_all_reminders():
    users = await database.get_all_users()
    for user in users:
        schedule_user(user["user_id"], user["remind_morning"], user["remind_evening"])
    logger.info("Загружено напоминаний для %d пользователей", len(users))
