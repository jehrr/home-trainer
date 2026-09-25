"""Хранилище SQLite: диалоги, сообщения, профиль атлета, заметки, сохранённые места."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Новый диалог',
    summary TEXT NOT NULL DEFAULT '',
    summarized_turns INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planned_workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL DEFAULT '',
    place TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'other',
    description TEXT NOT NULL DEFAULT '',
    duration_min INTEGER,
    target_tss INTEGER,
    indoor INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'planned',
    activity_id TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plan_date ON planned_workouts(date);
CREATE TABLE IF NOT EXISTS ride_feedback (
    activity_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    rpe INTEGER,
    feel INTEGER,
    note TEXT NOT NULL DEFAULT '',
    manual_duration_min INTEGER,
    manual_avg_hr INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS places (
    name TEXT PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
"""

# Стартовый профиль. Дальше тренер обновляет его сам по ходу разговоров.
DEFAULT_PROFILE = {
    "name": "Пётр",
    "age": "48",
    "weight_kg": "78",
    "height_cm": "186",
    "discipline": "шоссе",
    "ftp_w": "242",
    "ftp_goal_w": "272",
    "plan_start_date": "",
}

DEFAULT_NOTES = [
    "Каденс исторически низкий (58–76 об/мин), цель — 85–95.",
    "Сильный спринт: лучшие 5 с около 1080 Вт.",
    "Велокомпьютер Wahoo ELEMNT, файлы идут в Intervals через Dropbox. "
    "Активности из Strava через API Intervals недоступны.",
]

# Ключи профиля, которые разрешено менять
PROFILE_KEYS = {
    "name": "имя",
    "age": "возраст, лет",
    "weight_kg": "вес, кг",
    "height_cm": "рост, см",
    "discipline": "дисциплина",
    "ftp_w": "текущий FTP, Вт",
    "ftp_goal_w": "целевой FTP, Вт",
    "max_hr": "максимальный пульс",
    "lthr": "пульс на пороге (LTHR)",
    "plan_start_date": "дата начала 16-недельного плана (ГГГГ-ММ-ДД)",
    "target_event": "целевой старт и дата",
    "weekly_hours": "доступно часов в неделю",
    "default_place": "обычное место тренировок (имя сохранённого места)",
    "default_start_time": "обычное время старта (ЧЧ:ММ)",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(c) -> None:
    cols = {r[1] for r in c.execute("PRAGMA table_info(conversations)")}
    if "kind" not in cols:
        c.execute("ALTER TABLE conversations ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat'")
    if "day" not in cols:
        c.execute("ALTER TABLE conversations ADD COLUMN day TEXT NOT NULL DEFAULT ''")


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)
        _migrate(c)
        if c.execute("SELECT COUNT(*) FROM profile").fetchone()[0] == 0:
            for k, v in DEFAULT_PROFILE.items():
                c.execute("INSERT INTO profile(key, value, updated_at) VALUES (?,?,?)", (k, v, _now()))
            for text in DEFAULT_NOTES:
                c.execute("INSERT INTO notes(text, created_at) VALUES (?,?)", (text, _now()))


# ── Диалоги ──────────────────────────────────────────────

def create_conversation(title: str = "Новый диалог", kind: str = "chat", day: str = "") -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO conversations(title, kind, day, created_at, updated_at) VALUES (?,?,?,?,?)",
            (title, kind, day, _now(), _now()),
        )
        return cur.lastrowid


def find_conversation(kind: str, day: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM conversations WHERE kind = ? AND day = ? ORDER BY id DESC LIMIT 1",
                        (kind, day)).fetchone()
        return dict(row) if row else None


def list_conversations() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conv_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        return dict(row) if row else None


def rename_conversation(conv_id: int, title: str) -> None:
    with _conn() as c:
        c.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?", (title, _now(), conv_id))


def delete_conversation(conv_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def update_summary(conv_id: int, summary: str, summarized_turns: int) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE conversations SET summary = ?, summarized_turns = ? WHERE id = ?",
            (summary, summarized_turns, conv_id),
        )


# ── Сообщения ────────────────────────────────────────────

def next_turn(conv_id: int) -> int:
    with _conn() as c:
        row = c.execute("SELECT MAX(turn) FROM messages WHERE conversation_id = ?", (conv_id,)).fetchone()
        return (row[0] or 0) + 1


def add_message(conv_id: int, turn: int, role: str, content) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages(conversation_id, turn, role, content, created_at) VALUES (?,?,?,?,?)",
            (conv_id, turn, role, json.dumps(content, ensure_ascii=False), _now()),
        )
        c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), conv_id))


def get_messages(conv_id: int, after_turn: int = 0) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT turn, role, content FROM messages WHERE conversation_id = ? AND turn > ? ORDER BY id",
            (conv_id, after_turn),
        ).fetchall()
        return [{"turn": r["turn"], "role": r["role"], "content": json.loads(r["content"])} for r in rows]


# ── Профиль и заметки ────────────────────────────────────

def get_profile() -> dict:
    with _conn() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM profile")}


def set_profile(key: str, value: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO profile(key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, _now()),
        )


def list_notes() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT id, text, created_at FROM notes ORDER BY id")]


def add_note(text: str) -> int:
    with _conn() as c:
        return c.execute("INSERT INTO notes(text, created_at) VALUES (?,?)", (text, _now())).lastrowid


def delete_note(note_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM notes WHERE id = ?", (note_id,))


# ── Места ────────────────────────────────────────────────

def list_places() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT name, latitude, longitude, note FROM places ORDER BY name")]


def find_place(name: str) -> dict | None:
    # lower() в SQLite не понимает кириллицу, поэтому сравниваем в Python
    wanted = name.strip().casefold()
    for p in list_places():
        if p["name"].casefold() == wanted:
            return p
    return None


def save_place(name: str, latitude: float, longitude: float, note: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO places(name, latitude, longitude, note) VALUES (?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET latitude = excluded.latitude, "
            "longitude = excluded.longitude, note = excluded.note",
            (name.strip(), latitude, longitude, note),
        )


def delete_place(name: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM places WHERE name = ?", (name,))


# ── Локальный план ───────────────────────────────────────

PLAN_FIELDS = ("date", "start_time", "place", "title", "kind", "description", "duration_min",
               "target_tss", "indoor", "status", "activity_id", "notes")
PLAN_STATUSES = ("planned", "done", "partial", "missed", "skipped", "moved")
PLAN_KINDS = ("recovery", "endurance", "long", "tempo", "sweetspot", "threshold", "vo2max",
              "anaerobic", "sprint", "test", "race", "strength", "rest", "other")


def list_plan(date_from: str, date_to: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM planned_workouts WHERE date BETWEEN ? AND ? ORDER BY date, start_time, id",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]


def get_planned(workout_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM planned_workouts WHERE id = ?", (workout_id,)).fetchone()
        return dict(row) if row else None


def add_planned(item: dict) -> int:
    data = {k: item[k] for k in PLAN_FIELDS if k in item and item[k] is not None}
    data.setdefault("status", "planned")
    data["created_at"] = data["updated_at"] = _now()
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    with _conn() as c:
        return c.execute(f"INSERT INTO planned_workouts({cols}) VALUES ({marks})", tuple(data.values())).lastrowid


def update_planned(workout_id: int, fields: dict) -> None:
    data = {k: v for k, v in fields.items() if k in PLAN_FIELDS and v is not None}
    if not data:
        return
    data["updated_at"] = _now()
    sets = ", ".join(f"{k} = ?" for k in data)
    with _conn() as c:
        c.execute(f"UPDATE planned_workouts SET {sets} WHERE id = ?", (*data.values(), workout_id))


def delete_planned(workout_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM planned_workouts WHERE id = ?", (workout_id,))


# ── Ощущения после заезда ────────────────────────────────

def save_feedback(activity_id: str, day: str, rpe=None, feel=None, note: str = "",
                  manual_duration_min=None, manual_avg_hr=None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO ride_feedback(activity_id, date, rpe, feel, note, manual_duration_min, manual_avg_hr, created_at) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(activity_id) DO UPDATE SET "
            "date = excluded.date, rpe = COALESCE(excluded.rpe, ride_feedback.rpe), "
            "feel = COALESCE(excluded.feel, ride_feedback.feel), "
            "note = CASE WHEN excluded.note != '' THEN excluded.note ELSE ride_feedback.note END, "
            "manual_duration_min = COALESCE(excluded.manual_duration_min, ride_feedback.manual_duration_min), "
            "manual_avg_hr = COALESCE(excluded.manual_avg_hr, ride_feedback.manual_avg_hr)",
            (str(activity_id), day, rpe, feel, note or "", manual_duration_min, manual_avg_hr, _now()),
        )


def feedback_map(activity_ids: list) -> dict[str, dict]:
    ids = [str(i) for i in activity_ids if i]
    if not ids:
        return {}
    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM ride_feedback WHERE activity_id IN ({','.join('?' for _ in ids)})", ids
        ).fetchall()
        return {r["activity_id"]: dict(r) for r in rows}
