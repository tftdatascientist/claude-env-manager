from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


class LogStore:
    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    def _apply_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    def insert_event(
        self,
        session_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
        round: int | None = None,
        file_path: str | None = None,
        ts: str | None = None,
    ) -> int:
        ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
        cur = self._conn.execute(
            "INSERT INTO events (session_id, ts, round, kind, payload, file_path) VALUES (?,?,?,?,?,?)",
            (session_id, ts, round, kind, payload_json, file_path),
        )
        self._conn.commit()
        logger.debug("event inserted id=%s kind=%s session=%s", cur.lastrowid, kind, session_id)
        return cur.lastrowid  # type: ignore[return-value]

    def query_by_session(self, session_id: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY ts, id", (session_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def query_by_round(self, session_id: str, round: int) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? AND round = ? ORDER BY ts, id",
            (session_id, round),
        )
        return [dict(row) for row in cur.fetchall()]

    def query_by_kind(self, kind: str, session_id: str | None = None) -> list[dict]:
        if session_id:
            cur = self._conn.execute(
                "SELECT * FROM events WHERE session_id = ? AND kind = ? ORDER BY ts, id",
                (session_id, kind),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM events WHERE kind = ? ORDER BY ts, id", (kind,)
            )
        return [dict(row) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
