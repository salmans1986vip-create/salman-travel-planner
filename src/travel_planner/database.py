"""
طبقة قاعدة البيانات (SQLite).

الجداول:
    destinations   الوجهات وتكاليفها اليومية التقديرية
    activities     الأنشطة، كل نشاط مرتبط بوجهة
    trips          طلبات الرحلات والخطط المحفوظة (الخطة كاملة بصيغة JSON)
    plan_items     عناصر كل خطة (نشاط/يوم/فترة) لتسهيل الاستعلام
    chat_messages  سجل المحادثة لكل رحلة (ذاكرة LangChain للتعديلات)

كل الاستعلامات تستخدم معاملات (?) لمنع حقن SQL.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .exceptions import DatabaseUnavailableError
from .seed_data import ACTIVITIES, DESTINATIONS

SCHEMA = """
CREATE TABLE IF NOT EXISTS destinations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL UNIQUE,
    description       TEXT,
    hotel_night       REAL NOT NULL,
    food_per_person   REAL NOT NULL,
    transport_per_day REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id  INTEGER NOT NULL REFERENCES destinations(id),
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    duration_hours  REAL NOT NULL,
    cost_per_person REAL NOT NULL,
    best_time       TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS trips (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    destination  TEXT NOT NULL,
    days         INTEGER NOT NULL,
    travelers    INTEGER NOT NULL,
    budget       REAL NOT NULL,
    interests    TEXT NOT NULL,
    plan_json    TEXT,
    total_cost   REAL,
    source       TEXT DEFAULT 'llm',
    created_at   TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS plan_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id      INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number   INTEGER NOT NULL,
    time_slot    TEXT NOT NULL,
    activity_id  INTEGER NOT NULL REFERENCES activities(id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_activities_dest ON activities(destination_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
"""


class Database:
    """مستودع بيانات بسيط فوق SQLite."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------ اتصال
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """يفتح اتصالاً ويضمن الحفظ أو التراجع وإغلاق الاتصال."""
        try:
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
        except (sqlite3.Error, OSError) as exc:
            raise DatabaseUnavailableError(f"تعذّر فتح قاعدة البيانات: {exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseUnavailableError(f"خطأ في قاعدة البيانات: {exc}") from exc
        finally:
            conn.close()

    def initialize(self) -> None:
        """ينشئ الجداول ويعبّئ البيانات التجريبية عند أول تشغيل فقط."""
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            count = conn.execute("SELECT COUNT(*) FROM destinations").fetchone()[0]
            if count == 0:
                self._seed(conn)

    @staticmethod
    def _seed(conn: sqlite3.Connection) -> None:
        for d in DESTINATIONS:
            cur = conn.execute(
                "INSERT INTO destinations (name, description, hotel_night, food_per_person, transport_per_day)"
                " VALUES (?, ?, ?, ?, ?)",
                (d["name"], d["description"], d["hotel_night"], d["food_per_person"], d["transport_per_day"]),
            )
            dest_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO activities (destination_id, name, category, duration_hours,"
                " cost_per_person, best_time, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(dest_id, *a) for a in ACTIVITIES[d["name"]]],
            )

    # ------------------------------------------------------------- الوجهات
    def list_destinations(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM destinations ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get_destination(self, name: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM destinations WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------- الأنشطة
    def search_activities(self, destination: str, categories: list[str] | None = None) -> list[dict]:
        """يسترجع أنشطة الوجهة، مرتبة بحيث تأتي فئات اهتمام المستخدم أولاً."""
        sql = (
            "SELECT a.* FROM activities a JOIN destinations d ON d.id = a.destination_id"
            " WHERE d.name = ? ORDER BY a.id"
        )
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, (destination,)).fetchall()]
        if categories:
            # الأنشطة المطابقة للاهتمامات أولاً، ثم مطاعم (يحتاجها أي برنامج)، ثم البقية
            def rank(a: dict) -> int:
                if a["category"] in categories:
                    return 0
                return 1 if a["category"] == "food" else 2

            rows.sort(key=rank)
        return rows

    def get_activities_by_ids(self, ids: list[int]) -> dict[int, dict]:
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM activities WHERE id IN ({placeholders})", ids).fetchall()
        return {r["id"]: dict(r) for r in rows}

    # --------------------------------------------------------------- الرحلات
    def save_trip(self, request: dict, plan: dict, total_cost: float, source: str = "llm",
                  trip_id: int | None = None) -> int:
        """يحفظ رحلة جديدة أو يحدّث رحلة قائمة، مع عناصر الخطة."""
        plan_json = json.dumps(plan, ensure_ascii=False)
        interests = json.dumps(request["interests"], ensure_ascii=False)
        with self.connect() as conn:
            if trip_id is None:
                cur = conn.execute(
                    "INSERT INTO trips (destination, days, travelers, budget, interests, plan_json, total_cost, source)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (request["destination"], request["days"], request["travelers"], request["budget"],
                     interests, plan_json, total_cost, source),
                )
                trip_id = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE trips SET plan_json = ?, total_cost = ?, source = ?,"
                    " updated_at = datetime('now', 'localtime') WHERE id = ?",
                    (plan_json, total_cost, source, trip_id),
                )
                conn.execute("DELETE FROM plan_items WHERE trip_id = ?", (trip_id,))
            conn.executemany(
                "INSERT INTO plan_items (trip_id, day_number, time_slot, activity_id) VALUES (?, ?, ?, ?)",
                [
                    (trip_id, day["day_number"], item["time_slot"], item["activity_id"])
                    for day in plan["days"]
                    for item in day["items"]
                ],
            )
        return trip_id

    def list_trips(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, destination, days, travelers, budget, total_cost, source, created_at, updated_at"
                " FROM trips ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_trip(self, trip_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        if not row:
            return None
        trip = dict(row)
        trip["interests"] = json.loads(trip["interests"])
        trip["plan"] = json.loads(trip["plan_json"]) if trip["plan_json"] else None
        return trip

    def delete_trip(self, trip_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (f"trip-{trip_id}",))
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))

    # -------------------------------------------------------------- المحادثة
    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def get_messages(self, session_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id", (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_messages(self, session_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
