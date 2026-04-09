import aiosqlite
import os
from datetime import datetime
import pytz

from config import DB_PATH, TIMEZONE

MSK = pytz.timezone(TIMEZONE)


def now_msk() -> datetime:
    """Текущее время по МСК (naive datetime для хранения в БД)."""
    return datetime.now(tz=MSK).replace(tzinfo=None)


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT,
                remind_morning  TEXT DEFAULT '09:00',
                remind_evening  TEXT DEFAULT '21:00',
                created_at      TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER REFERENCES users(user_id),
                systolic    INTEGER NOT NULL,
                diastolic   INTEGER NOT NULL,
                pulse       INTEGER,
                note        TEXT,
                measured_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def register_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, created_at) VALUES (?, ?, ?)",
            (user_id, username, now_msk().isoformat()),
        )
        await db.commit()


async def add_measurement(
    user_id: int,
    systolic: int,
    diastolic: int,
    pulse: int | None = None,
    note: str | None = None,
    measured_at: datetime | None = None,
):
    ts = (measured_at or now_msk()).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO measurements (user_id, systolic, diastolic, pulse, note, measured_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, systolic, diastolic, pulse, note, ts),
        )
        await db.commit()


async def add_measurements_bulk(user_id: int, rows: list[dict]):
    """Массовая вставка записей. Каждый dict: systolic, diastolic, pulse, note, measured_at."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO measurements (user_id, systolic, diastolic, pulse, note, measured_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (user_id, r["systolic"], r["diastolic"], r.get("pulse"), r.get("note"), r["measured_at"].isoformat())
                for r in rows
            ],
        )
        await db.commit()


async def get_history(user_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM measurements WHERE user_id = ? ORDER BY measured_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_measurement(measurement_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM measurements WHERE id = ? AND user_id = ?",
            (measurement_id, user_id),
        )
        await db.commit()


async def clear_all_measurements(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM measurements WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_total_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM measurements WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0


async def get_measurements_since(user_id: int, since: datetime) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM measurements WHERE user_id = ? AND measured_at >= ? ORDER BY measured_at ASC",
            (user_id, since.isoformat()),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_remind_times(user_id: int, morning: str, evening: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET remind_morning = ?, remind_evening = ? WHERE user_id = ?",
            (morning, evening, user_id),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None
