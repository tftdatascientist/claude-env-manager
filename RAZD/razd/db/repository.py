from __future__ import annotations

import json
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
class FocusSession:
    id: int
    started_at: str
    ended_at: str | None
    duration_s: int
    score: int | None
    whitelist_snapshot: str


@dataclass
class CcSession:
    id: int
    project_path: str
    started_at: str
    ended_at: str | None
    duration_s: int


@dataclass
class BreakEvent:
    id: int
    ts: str
    minutes_worked: int
    event_type: str  # suggested | taken | skipped


@dataclass
class DistractionEvent:
    id: int
    ts: str
    switches_per_min: float
    duration_s: int


@dataclass
class DailyReport:
    date: str
    total_active_s: int
    productive_s: int
    idle_s: int
    productivity_score: int  # 0-100
    top_categories: list[tuple[str, int]]  # (name, seconds)
    focus_sessions: list[FocusSession]
    cc_sessions: list[CcSession]
    break_events: list[BreakEvent]
    distraction_events: list[DistractionEvent]


@dataclass
class UserDecision:
    id: int
    subject: str
    subject_type: str
    question: str
    answer: str
    category_id: int | None
    decided_at: str


@dataclass
class WebVisit:
    id: int
    url: str
    domain: str
    page_title: str | None
    browser: str | None
    category_id: int | None
    first_seen_at: str
    last_seen_at: str
    visit_count: int
    total_time_s: int


@dataclass
class DomainSummary:
    domain: str
    url_count: int
    total_visits: int
    total_time_s: int
    last_seen_at: str
    browsers: str


@dataclass
class AppUsage:
    id: int
    process_name: str
    exe_path: str | None
    category_id: int | None
    first_seen_at: str
    last_seen_at: str
    total_time_s: int
    today_time_s: int
    focus_switches: int
    is_dev_tool: bool


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

    def get_events_for_range(self, start_ts: float, end_ts: float) -> list[Event]:
        """Zwraca eventy z zakresu [start_ts, end_ts] (unix timestamps)."""
        import datetime as _dt
        start_iso = _dt.datetime.fromtimestamp(start_ts).isoformat(timespec="seconds")
        end_iso = _dt.datetime.fromtimestamp(end_ts).isoformat(timespec="seconds")
        rows = self._conn.execute(
            "SELECT * FROM events WHERE ts >= ? AND ts <= ? ORDER BY ts",
            (start_iso, end_iso),
        ).fetchall()
        return [_row_to_event(r) for r in rows]

    def get_focus_sessions_for_range(self, start_ts: float, end_ts: float) -> list[FocusSession]:
        """Zwraca sesje focus nachodzące na zakres [start_ts, end_ts]."""
        import datetime as _dt
        start_iso = _dt.datetime.fromtimestamp(start_ts).isoformat(timespec="seconds")
        end_iso = _dt.datetime.fromtimestamp(end_ts).isoformat(timespec="seconds")
        rows = self._conn.execute(
            "SELECT id, started_at, ended_at, duration_s, score, whitelist_snapshot"
            " FROM focus_sessions"
            " WHERE started_at <= ? AND (ended_at IS NULL OR ended_at >= ?)"
            " ORDER BY started_at",
            (end_iso, start_iso),
        ).fetchall()
        return [
            FocusSession(r["id"], r["started_at"], r["ended_at"], r["duration_s"],
                         r["score"], r["whitelist_snapshot"])
            for r in rows
        ]

    # --- Focus sessions ---

    def start_focus_session(self, started_at: str, whitelist: set[str]) -> int:
        cur = self._conn.execute(
            "INSERT INTO focus_sessions(started_at, whitelist_snapshot) VALUES(?,?) RETURNING id",
            (started_at, json.dumps(sorted(whitelist))),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    def end_focus_session(self, session_id: int, ended_at: str, duration_s: int, score: int) -> None:
        self._conn.execute(
            "UPDATE focus_sessions SET ended_at=?, duration_s=?, score=? WHERE id=?",
            (ended_at, duration_s, score, session_id),
        )
        self._conn.commit()

    def add_focus_process_sample(self, session_id: int, ts: str, process_name: str) -> None:
        self._conn.execute(
            "INSERT INTO focus_process_samples(session_id, ts, process_name) VALUES(?,?,?)",
            (session_id, ts, process_name),
        )
        self._conn.commit()

    def get_focus_process_samples(self, session_id: int) -> list[tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT ts, process_name FROM focus_process_samples WHERE session_id=? ORDER BY ts",
            (session_id,),
        ).fetchall()
        return [(r["ts"], r["process_name"]) for r in rows]

    def get_focus_sessions_for_day(self, date: str) -> list[FocusSession]:
        rows = self._conn.execute(
            "SELECT id, started_at, ended_at, duration_s, score, whitelist_snapshot"
            " FROM focus_sessions WHERE started_at LIKE ? ORDER BY started_at",
            (f"{date}%",),
        ).fetchall()
        return [
            FocusSession(r["id"], r["started_at"], r["ended_at"], r["duration_s"], r["score"], r["whitelist_snapshot"])
            for r in rows
        ]

    # --- CC sessions ---

    def open_cc_session(self, project_path: str, started_at: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO cc_sessions(project_path, started_at) VALUES(?,?) RETURNING id",
            (project_path, started_at),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    def close_cc_session(self, session_id: int, ended_at: str, duration_s: int) -> None:
        self._conn.execute(
            "UPDATE cc_sessions SET ended_at=?, duration_s=? WHERE id=?",
            (ended_at, duration_s, session_id),
        )
        self._conn.commit()

    def add_cc_snapshot(self, session_id: int, ts: str, pid: int, exe: str) -> None:
        self._conn.execute(
            "INSERT INTO cc_snapshots(session_id, ts, pid, exe) VALUES(?,?,?,?)",
            (session_id, ts, pid, exe),
        )
        self._conn.commit()

    def get_cc_sessions_for_day(self, date: str) -> list[CcSession]:
        rows = self._conn.execute(
            "SELECT id, project_path, started_at, ended_at, duration_s"
            " FROM cc_sessions WHERE started_at LIKE ? ORDER BY started_at",
            (f"{date}%",),
        ).fetchall()
        return [
            CcSession(r["id"], r["project_path"], r["started_at"], r["ended_at"], r["duration_s"])
            for r in rows
        ]

    # --- Break events ---

    def add_break_event(self, ts: str, minutes_worked: int, event_type: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO break_events(ts, minutes_worked, event_type) VALUES(?,?,?) RETURNING id",
            (ts, minutes_worked, event_type),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    def get_break_events_for_day(self, date: str) -> list[BreakEvent]:
        rows = self._conn.execute(
            "SELECT id, ts, minutes_worked, event_type FROM break_events WHERE ts LIKE ? ORDER BY ts",
            (f"{date}%",),
        ).fetchall()
        return [BreakEvent(r["id"], r["ts"], r["minutes_worked"], r["event_type"]) for r in rows]

    # --- Distraction events ---

    def add_distraction_event(self, ts: str, switches_per_min: float, duration_s: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO distraction_events(ts, switches_per_min, duration_s) VALUES(?,?,?) RETURNING id",
            (ts, switches_per_min, duration_s),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row["id"]

    def get_distraction_events_for_day(self, date: str) -> list[DistractionEvent]:
        rows = self._conn.execute(
            "SELECT id, ts, switches_per_min, duration_s FROM distraction_events WHERE ts LIKE ? ORDER BY ts",
            (f"{date}%",),
        ).fetchall()
        return [DistractionEvent(r["id"], r["ts"], r["switches_per_min"], r["duration_s"]) for r in rows]

    # --- Daily report ---

    def get_daily_report(self, date: str) -> DailyReport:
        events = self.get_events_for_day(date)
        cats = {c.id: c for c in self.list_categories()}

        total_active_s = 0
        productive_s = 0
        idle_s = 0
        cat_seconds: dict[str, int] = {}

        for i, ev in enumerate(events):
            next_ts = (
                _parse_ts(events[i + 1].ts) if i + 1 < len(events)
                else _parse_ts(ev.ts) + 2
            )
            duration = min(int(next_ts - _parse_ts(ev.ts)), 120)
            if duration <= 0:
                continue
            if ev.event_type == "idle":
                idle_s += duration
            else:
                total_active_s += duration
                cat = cats.get(ev.category_id) if ev.category_id else None
                cat_name = cat.name if cat else (ev.process_name or "Inne")
                cat_seconds[cat_name] = cat_seconds.get(cat_name, 0) + duration
                if cat and cat.is_productive:
                    productive_s += duration

        top_categories = sorted(cat_seconds.items(), key=lambda x: -x[1])[:5]
        score = round(productive_s / total_active_s * 100) if total_active_s > 0 else 0

        return DailyReport(
            date=date,
            total_active_s=total_active_s,
            productive_s=productive_s,
            idle_s=idle_s,
            productivity_score=min(100, score),
            top_categories=top_categories,
            focus_sessions=self.get_focus_sessions_for_day(date),
            cc_sessions=self.get_cc_sessions_for_day(date),
            break_events=self.get_break_events_for_day(date),
            distraction_events=self.get_distraction_events_for_day(date),
        )

    # --- Web visits ---

    def record_web_visit(
        self,
        url: str,
        title: str | None,
        browser: str | None,
        ts: str,
        new_visit: bool,
    ) -> None:
        domain = _extract_domain(url)
        delta = 1 if new_visit else 0
        self._conn.execute(
            "INSERT INTO web_visits(url, domain, page_title, browser, first_seen_at, last_seen_at,"
            " visit_count, total_time_s) VALUES(?,?,?,?,?,?,?,2)"
            " ON CONFLICT(url) DO UPDATE SET"
            "  last_seen_at=excluded.last_seen_at,"
            "  visit_count=visit_count+?,"
            "  total_time_s=total_time_s+2,"
            "  page_title=COALESCE(excluded.page_title, page_title),"
            "  browser=COALESCE(excluded.browser, browser)",
            (url, domain, title, browser, ts, ts, max(delta, 1), delta),
        )
        self._conn.commit()

    def record_app_usage(
        self,
        process_name: str,
        ts: str,
        is_focus_switch: bool,
        exe_path: str | None = None,
    ) -> None:
        is_dev = int(process_name.lower() in _DEV_TOOL_NAMES)
        delta = 1 if is_focus_switch else 0
        self._conn.execute(
            "INSERT INTO app_usage(process_name, exe_path, first_seen_at, last_seen_at,"
            " total_time_s, focus_switches, is_dev_tool) VALUES(?,?,?,?,2,?,?)"
            " ON CONFLICT(process_name) DO UPDATE SET"
            "  last_seen_at=excluded.last_seen_at,"
            "  total_time_s=total_time_s+2,"
            "  focus_switches=focus_switches+?,"
            "  is_dev_tool=max(is_dev_tool, excluded.is_dev_tool),"
            "  exe_path=COALESCE(excluded.exe_path, exe_path)",
            (process_name, exe_path, ts, ts, delta, is_dev, delta),
        )
        self._conn.commit()

    def get_domains(self, date_filter: str | None = None) -> list[DomainSummary]:
        if date_filter:
            rows = self._conn.execute(
                "SELECT domain, COUNT(DISTINCT url) url_count, SUM(visit_count) total_visits,"
                " SUM(total_time_s) total_time, MAX(last_seen_at) last_seen,"
                " GROUP_CONCAT(DISTINCT browser) browsers"
                " FROM web_visits WHERE last_seen_at LIKE ?"
                " GROUP BY domain ORDER BY total_time DESC",
                (f"{date_filter}%",),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT domain, COUNT(DISTINCT url) url_count, SUM(visit_count) total_visits,"
                " SUM(total_time_s) total_time, MAX(last_seen_at) last_seen,"
                " GROUP_CONCAT(DISTINCT browser) browsers"
                " FROM web_visits GROUP BY domain ORDER BY total_time DESC"
            ).fetchall()
        return [
            DomainSummary(r["domain"], r["url_count"], r["total_visits"],
                          r["total_time"], r["last_seen"], r["browsers"] or "")
            for r in rows
        ]

    def get_urls_for_domain(self, domain: str) -> list[WebVisit]:
        rows = self._conn.execute(
            "SELECT id, url, domain, page_title, browser, category_id,"
            " first_seen_at, last_seen_at, visit_count, total_time_s"
            " FROM web_visits WHERE domain=? ORDER BY total_time_s DESC",
            (domain,),
        ).fetchall()
        return [_row_to_web_visit(r) for r in rows]

    def search_urls(self, query: str) -> list[WebVisit]:
        like = f"%{query}%"
        rows = self._conn.execute(
            "SELECT id, url, domain, page_title, browser, category_id,"
            " first_seen_at, last_seen_at, visit_count, total_time_s"
            " FROM web_visits WHERE url LIKE ? OR page_title LIKE ? OR domain LIKE ?"
            " ORDER BY total_time_s DESC LIMIT 200",
            (like, like, like),
        ).fetchall()
        return [_row_to_web_visit(r) for r in rows]

    def get_app_usage_list(self, dev_only: bool = False, date_filter: str | None = None) -> list[AppUsage]:
        today = date_filter or __import__('datetime').date.today().isoformat()
        # today_time_s from events table
        today_rows = self._conn.execute(
            "SELECT process_name, COUNT(*)*2 as today_s FROM events"
            " WHERE ts LIKE ? AND event_type != 'idle' AND process_name IS NOT NULL"
            " GROUP BY process_name",
            (f"{today}%",),
        ).fetchall()
        today_map = {r["process_name"]: r["today_s"] for r in today_rows}

        if dev_only:
            rows = self._conn.execute(
                "SELECT id, process_name, exe_path, category_id, first_seen_at,"
                " last_seen_at, total_time_s, focus_switches, is_dev_tool"
                " FROM app_usage WHERE is_dev_tool=1 ORDER BY total_time_s DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, process_name, exe_path, category_id, first_seen_at,"
                " last_seen_at, total_time_s, focus_switches, is_dev_tool"
                " FROM app_usage ORDER BY total_time_s DESC"
            ).fetchall()
        return [
            AppUsage(
                r["id"], r["process_name"], r["exe_path"], r["category_id"],
                r["first_seen_at"], r["last_seen_at"], r["total_time_s"],
                today_map.get(r["process_name"], 0),
                r["focus_switches"], bool(r["is_dev_tool"]),
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


_DEV_TOOL_NAMES = frozenset({
    "code.exe", "code",
    "cc.exe", "cc", "claude.exe", "claude",
    "cursor.exe", "cursor",
    "node.exe", "node",
    "python.exe", "python", "python3", "python3.exe",
    "git.exe", "git",
    "cmd.exe", "powershell.exe", "pwsh.exe",
    "windowsterminal.exe", "wt.exe",
    "notepad++.exe",
    "idea64.exe", "pycharm64.exe", "webstorm64.exe",
    "devenv.exe",
    "postman.exe",
    "docker.exe", "docker desktop.exe",
    "gh.exe", "gh",
})


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc or url
        if host.startswith("www."):
            host = host[4:]
        return host.split(":")[0].lower()
    except Exception:
        return url[:60]


def _row_to_web_visit(row: sqlite3.Row) -> WebVisit:
    return WebVisit(
        row["id"], row["url"], row["domain"], row["page_title"], row["browser"],
        row["category_id"], row["first_seen_at"], row["last_seen_at"],
        row["visit_count"], row["total_time_s"],
    )


def _parse_ts(ts: str) -> float:
    from datetime import datetime
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return 0.0


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
