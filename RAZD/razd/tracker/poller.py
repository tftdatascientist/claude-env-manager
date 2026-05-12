from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from razd.tracker.active_window import get_active_window
from razd.tracker.break_engine import RazdBreakEngine
from razd.tracker.browser_url import BROWSER_PROCESSES, get_browser_url, sanitize_url
from razd.tracker.cc_scanner import CcProcessDTO, scan_cc_processes
from razd.tracker.distraction_detector import RazdDistractionDetector
from razd.tracker.idle import get_idle_seconds

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository

POLL_INTERVAL_MS = 2000
IDLE_THRESHOLD_S = 60.0


@dataclass
class EventDTO:
    ts: str
    event_type: str          # "active" | "idle" | "browser"
    process_name: str | None
    window_title: str | None
    url: str | None
    idle_seconds: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class _CcSessionTracker:
    """Śledzi aktywne sesje Claude Code przez diff zbiorów project_path."""

    def __init__(self, repo: RazdRepository | None) -> None:
        self._repo = repo
        # project_path → (session_id, started_at_iso)
        self._active: dict[str, tuple[int, str]] = {}
        self._prev_paths: set[str] = set()

    def update(
        self, dtos: set[CcProcessDTO]
    ) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
        """
        Porównuje bieżące procesy z poprzednim stanem.
        Zwraca (started, ended):
          started: [(project_path, session_id), ...]
          ended:   [(project_path, duration_s), ...]
        """
        now_iso = datetime.now().isoformat(timespec="seconds")
        now_ts = datetime.now().timestamp()
        current_paths = {d.project_path for d in dtos}

        started: list[tuple[str, int]] = []
        ended: list[tuple[str, int]] = []

        for path in current_paths - self._prev_paths:
            session_id = self._repo.open_cc_session(path, now_iso) if self._repo else 0
            self._active[path] = (session_id, now_iso)
            started.append((path, session_id))

        for path in self._prev_paths - current_paths:
            if path in self._active:
                session_id, started_iso = self._active.pop(path)
                started_ts = datetime.fromisoformat(started_iso).timestamp()
                duration_s = max(0, round(now_ts - started_ts))
                if self._repo and session_id:
                    self._repo.close_cc_session(session_id, now_iso, duration_s)
                ended.append((path, duration_s))

        # snapshoty dla ciągle aktywnych
        if self._repo:
            for dto in dtos:
                session_id, _ = self._active.get(dto.project_path, (0, ""))
                if session_id:
                    self._repo.add_cc_snapshot(session_id, now_iso, dto.pid, dto.exe)

        self._prev_paths = current_paths
        return started, ended

    @property
    def active_paths(self) -> set[str]:
        return set(self._active.keys())


class RazdPoller(QObject):
    """Polling co 2s — emituje event_ready z EventDTO i sygnały sesji CC."""

    event_ready = Signal(object)           # EventDTO
    cc_session_started = Signal(str, int)  # project_path, session_id
    cc_session_ended = Signal(str, int)    # project_path, duration_s
    break_due = Signal(int)               # minutes_worked
    distraction_alert = Signal(float)     # switches_per_min
    distraction_score = Signal(float)     # switches_per_min (każdy poll)

    def __init__(
        self,
        repo: RazdRepository | None = None,
        work_interval_min: int = 50,
        distraction_threshold: float = 6.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._cc_tracker = _CcSessionTracker(repo)
        self._break_engine = RazdBreakEngine(work_interval_min)
        self._break_engine.break_due.connect(self._on_break_due)
        self._distraction = RazdDistractionDetector(distraction_threshold)
        self._distraction.distraction_alert.connect(self._on_distraction_alert)
        self._distraction.score_updated.connect(self.distraction_score)
        self._prev_url: str | None = None
        self._prev_process: str | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    @property
    def active_cc_paths(self) -> set[str]:
        return self._cc_tracker.active_paths

    @property
    def break_engine(self) -> RazdBreakEngine:
        return self._break_engine

    def confirm_break_taken(self) -> None:
        """Wołane z UI gdy user potwierdza wzięcie przerwy."""
        minutes = self._break_engine.take_break()
        if self._repo:
            ts = datetime.now().isoformat(timespec="seconds")
            self._repo.add_break_event(ts, minutes, "taken")

    def _on_break_due(self, minutes: int) -> None:
        if self._repo:
            ts = datetime.now().isoformat(timespec="seconds")
            self._repo.add_break_event(ts, minutes, "suggested")
        self.break_due.emit(minutes)

    def _on_distraction_alert(self, spm: float) -> None:
        if self._repo:
            ts = datetime.now().isoformat(timespec="seconds")
            self._repo.add_distraction_event(ts, round(spm, 2), 60)
        self.distraction_alert.emit(spm)

    def _poll(self) -> None:
        idle = get_idle_seconds()
        event_type = "idle" if idle >= IDLE_THRESHOLD_S else "active"

        window = get_active_window()
        process_name = window.process_name if window else None
        window_title = window.window_title if window else None

        url: str | None = None
        if process_name and process_name.lower() in BROWSER_PROCESSES and event_type == "active":
            url = get_browser_url(process_name)
            if url:
                event_type = "browser"

        dto = EventDTO(
            ts=datetime.now().isoformat(timespec="seconds"),
            event_type=event_type,
            process_name=process_name,
            window_title=window_title,
            url=url,
            idle_seconds=round(idle, 1),
        )
        self.event_ready.emit(dto)
        if self._repo:
            now_iso = datetime.now().isoformat(timespec="seconds")
            cat_id: int | None = None
            if dto.url:
                cat_id = self._repo.get_category_for_url(dto.url)
            if cat_id is None and dto.process_name:
                cat_id = self._repo.get_category_for_process(dto.process_name)
            self._repo.insert_event(
                ts=dto.ts,
                event_type=dto.event_type,
                raw_json=dto.to_json(),
                process_name=dto.process_name,
                window_title=dto.window_title,
                url=dto.url,
                idle_seconds=int(dto.idle_seconds),
                category_id=cat_id,
            )
            if dto.event_type != "idle":
                new_url = dto.url != self._prev_url
                new_proc = dto.process_name != self._prev_process
                if dto.url:
                    self._repo.record_web_visit(dto.url, dto.window_title, dto.process_name, now_iso, new_url)
                if dto.process_name:
                    self._repo.record_app_usage(dto.process_name, now_iso, new_proc)
        self._prev_url = dto.url
        self._prev_process = dto.process_name if dto.event_type != "idle" else self._prev_process
        self._break_engine.feed(dto)
        self._distraction.feed(dto)

        # skanuj procesy CC i emituj zmiany sesji
        cc_dtos = scan_cc_processes()
        started, ended = self._cc_tracker.update(cc_dtos)
        for path, session_id in started:
            self.cc_session_started.emit(path, session_id)
        for path, duration_s in ended:
            self.cc_session_ended.emit(path, duration_s)
