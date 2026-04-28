from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QTimer, Signal

from razd.tracker.active_window import get_active_window
from razd.tracker.browser_url import BROWSER_PROCESSES, get_browser_url, sanitize_url
from razd.tracker.idle import get_idle_seconds

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


class RazdPoller(QObject):
    """Polling co 2s — emituje event_ready z EventDTO."""

    event_ready = Signal(object)   # EventDTO

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

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
            ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            event_type=event_type,
            process_name=process_name,
            window_title=window_title,
            url=url,
            idle_seconds=round(idle, 1),
        )
        self.event_ready.emit(dto)
