import re
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import database
import scheduler as sched
from charts import build_chart, PERIODS

logger = logging.getLogger(__name__)

# Regex: "120/80" or "120/80 72" or "120/80 72 note here"
BP_PATTERN = re.compile(
    r"(\d{2,3})\s*/\s*(\d{2,3})(?:\s+(\d{2,3}))?(?:\s+(.+))?"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await database.register_user(user.id, user.username or user.first_name)
    sched.schedule_user(user.id, "09:00", "21:00")

    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Я помогу отслеживать твоё давление и пульс.\n\n"
        "<b>Как записать замер:</b>\n"
        "Просто отправь сообщение вида:\n"
        "<code>120/80 72</code>  — давление и пульс\n"
        "<code>120/80</code>      — только давление\n\n"
        "<b>Команды:</b>\n"
        "/history — последние 10 записей\n"
        "/chart — график давления\n"
        "/remind — изменить время напоминаний\n"
        "/help — справка\n\n"
        "Напоминания настроены на <b>09:00</b> и <b>21:00</b>.",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Команды бота:</b>\n\n"
        "/start — регистрация и приветствие\n"
        "/history [N] — последние N записей (по умолч. 10)\n"
        "/chart [week|month|3months] — график\n"
        "/remind HH:MM HH:MM — изменить время напоминаний\n"
        "  пример: /remind 08:30 22:00\n\n"
        "<b>Добавить замер:</b>\n"
        "Отправь сообщение: <code>120/80 72</code>",
        parse_mode="HTML",
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await database.register_user(user_id, update.effective_user.username or "")

    limit = 10
    if context.args:
        try:
            limit = max(1, min(int(context.args[0]), 50))
        except ValueError:
            pass

    records = await database.get_history(user_id, limit)
    if not records:
        await update.message.reply_text("Записей пока нет. Отправь замер в формате <code>120/80 72</code>.", parse_mode="HTML")
        return

    lines = [f"<b>Последние {len(records)} записей:</b>\n"]
    for r in records:
        dt = datetime.fromisoformat(r["measured_at"]).strftime("%d.%m.%Y %H:%M")
        pulse_str = f"  пульс: {r['pulse']}" if r["pulse"] else ""
        note_str = f"  📝 {r['note']}" if r["note"] else ""
        lines.append(f"<b>{dt}</b>\n  {r['systolic']}/{r['diastolic']} мм рт.ст.{pulse_str}{note_str}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await database.register_user(user_id, update.effective_user.username or "")

    period = "week"
    if context.args and context.args[0] in PERIODS:
        period = context.args[0]

    if not context.args or context.args[0] not in PERIODS:
        keyboard = [
            [
                InlineKeyboardButton("7 дней", callback_data="chart_week"),
                InlineKeyboardButton("30 дней", callback_data="chart_month"),
                InlineKeyboardButton("90 дней", callback_data="chart_3months"),
            ]
        ]
        await update.message.reply_text(
            "Выбери период для графика:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await _send_chart(update.message, user_id, period)


async def chart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    period = query.data.replace("chart_", "")
    user_id = update.effective_user.id
    await _send_chart(query.message, user_id, period)


async def _send_chart(message, user_id: int, period: str):
    days = PERIODS[period]
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    since_naive = since.replace(tzinfo=None)

    records = await database.get_measurements_since(user_id, since_naive)
    if len(records) < 2:
        await message.reply_text(
            f"Недостаточно данных за выбранный период (нужно минимум 2 записи).\n"
            "Добавь замеры командой: <code>120/80 72</code>",
            parse_mode="HTML",
        )
        return

    buf = build_chart(records, period)
    await message.reply_photo(photo=buf, caption=f"График давления за период")


async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await database.register_user(user_id, update.effective_user.username or "")

    time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

    if len(context.args) != 2 or not time_pattern.match(context.args[0]) or not time_pattern.match(context.args[1]):
        await update.message.reply_text(
            "Формат: /remind HH:MM HH:MM\n"
            "Пример: /remind 08:30 21:00",
        )
        return

    morning, evening = context.args[0], context.args[1]
    await database.update_remind_times(user_id, morning, evening)
    sched.schedule_user(user_id, morning, evening)

    await update.message.reply_text(
        f"Напоминания обновлены:\n"
        f"Утро: <b>{morning}</b>\n"
        f"Вечер: <b>{evening}</b>",
        parse_mode="HTML",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = BP_PATTERN.search(text)

    if not match:
        await update.message.reply_text(
            "Не понял. Отправь замер в формате:\n"
            "<code>120/80 72</code>  или  <code>120/80</code>",
            parse_mode="HTML",
        )
        return

    user_id = update.effective_user.id
    await database.register_user(user_id, update.effective_user.username or "")

    systolic = int(match.group(1))
    diastolic = int(match.group(2))
    pulse = int(match.group(3)) if match.group(3) else None
    note = match.group(4).strip() if match.group(4) else None

    if not (60 <= systolic <= 250 and 40 <= diastolic <= 150):
        await update.message.reply_text("Похоже на ошибку в значениях. Проверь: систолическое 60-250, диастолическое 40-150.")
        return

    await database.add_measurement(user_id, systolic, diastolic, pulse, note)

    pulse_str = f"\nПульс: <b>{pulse}</b> уд/мин" if pulse else ""
    note_str = f"\nЗаметка: {note}" if note else ""
    eval_str = _evaluate_bp(systolic, diastolic)

    await update.message.reply_text(
        f"Записано!\n\n"
        f"Давление: <b>{systolic}/{diastolic}</b> мм рт. ст.{pulse_str}{note_str}\n\n"
        f"{eval_str}",
        parse_mode="HTML",
    )


def _evaluate_bp(sys: int, dia: int) -> str:
    if sys < 90 or dia < 60:
        return "Давление низкое (гипотония)."
    elif sys <= 120 and dia <= 80:
        return "Отлично! Давление в норме."
    elif sys <= 129 and dia < 80:
        return "Давление немного повышено."
    elif sys <= 139 or dia <= 89:
        return "Высокое нормальное давление."
    else:
        return "Давление повышено. Рекомендуется проконсультироваться с врачом."


def register_handlers(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("chart", cmd_chart))
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(CallbackQueryHandler(chart_callback, pattern=r"^chart_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
