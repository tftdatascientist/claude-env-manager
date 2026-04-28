from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


_SCHEMA = Path(__file__).parent / "schema.sql"


@dataclass
class Category:
    id: int
    name: str
    color: str
    is_productive: bool


@dataclass
class Event:
    id: int
    ts: str
    event_type: str
    process_name: str | None
    window_title: str | None
    url: str | None
    idle_seconds: int
    category_id: int | None
    raw_json: str


@dataclass
class UserDecision:
    id: int
    subject: str
    subject_type: str
    question: str
    answer: str
    category_id: int | None
    decided_at: str


class RazdRepository:
    """Dostęp do lokalnej bazy SQLite RAZD. Jedna instancja per wątek."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._apply_schema()

    def _apply_schema(self) -> None:
        self._conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        self._conn.commit()

    # --- Categories ---

    def upsert_category(self, name: str, color: str = "#888888", is_productive: bool = True) -> int:
        cur = self._conn.execute(
            "INSERT INTO categories(name, color, is_productive) VALUES(?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET color=excluded.color, is_productive=excluded.is_productive"
            " RETURNING id",
            (name, color, int(is_productive)),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    def get_category_by_name(self, name: str) -> Category | None:
        row = self._conn.execute(
            "SELECT id, name, color, is_productive FROM categories WHERE name=?", (name,)
        ).fetchone()
        if row is None:
            return None
        return Category(row["id"], row["name"], row["color"], bool(row["is_productive"]))

    def list_categories(self) -> list[Category]:
        rows = self._conn.execute(
            "SELECT id, name, color, is_productive FROM categories ORDER BY name"
        ).fetchall()
        return [Category(r["id"], r["name"], r["color"], bool(r["is_productive"])) for r in rows]

    # --- Processes ---

    def upsert_process(self, name: str, category_id: int | None = None) -> None:
        self._conn.execute(
            "INSERT INTO processes(name, category_id) VALUES(?,?)"
            " ON CONFLICT(name) DO UPDATE SET category_id=COALESCE(excluded.category_id, category_id)",
            (name, category_id),
        )
        self._conn.commit()

    def get_category_for_process(self, process_name: str) -> int | None:
        row = self._conn.execute(
            "SELECT category_id FROM processes WHERE name=?", (process_name,)
        ).fetchone()
        return row["category_id"] if row else None

    # --- URL mappings ---

    def upsert_url_mapping(self, pattern: str, category_id: int) -> None:
        self._conn.execute(
            "INSERT INTO url_mappings(pattern, category_id) VALUES(?,?)"
            " ON CONFLICT(pattern) DO UPDATE SET category_id=excluded.category_id",
            (pattern, category_id),
        )
        self._conn.commit()

    def get_category_for_url(self, url: str) -> int | None:
        rows = self._conn.execute(
            "SELECT pattern, category_id FROM url_mappings"
        ).fetchall()
        for row in rows:
            if row["pattern"] in url:
                return row["category_id"]
        return None

    # --- User decisions ---

    def save_decision(
        self,
        subject: str,
        subject_type: str,
        question: str,
        answer: str,
        category_id: int | None = None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO user_decisions(subject, subject_type, question, answer, category_id)"
            " VALUES(?,?,?,?,?) RETURNING id",
            (subject, subject_type, question, answer, category_id),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    # --- Events ---

    def insert_event(
        self,
        ts: str,
        event_type: str,
        raw_json: str,
        process_name: str | None = None,
        window_title: str | None = None,
        url: str | None = None,
        idle_seconds: int = 0,
        category_id: int | None = None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO events(ts, event_type, process_name, window_title, url,"
            " idle_seconds, category_id, raw_json) VALUES(?,?,?,?,?,?,?,?) RETURNING id",
            (ts, event_type, process_name, window_title, url, idle_seconds, category_id, raw_json),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    def get_events_for_day(self, date: str) -> list[Event]:
        """date w formacie YYYY-MM-DD."""
        rows = self._conn.execute(
            "SELECT * FROM events WHERE ts LIKE ? ORDER BY ts",
            (f"{date}%",),
        ).fetchall()
        return [_row_to_event(r) for r in rows]

    def close(self) -> None:
        self._conn.close()


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        ts=row["ts"],
        event_type=row["event_type"],
        process_name=row["process_name"],
        window_title=row["window_title"],
        url=row["url"],
        idle_seconds=row["idle_seconds"],
        category_id=row["category_id"],
        raw_json=row["raw_json"],
    )
