from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

_SECTION_RE = re.compile(
    r"<!--\s*SECTION:(?P<name>\w+)\s*-->(?P<body>.*?)<!--\s*/SECTION:\w+\s*-->",
    re.DOTALL,
)


def _parse_plan(text: str) -> dict[str, str]:
    return {m.group("name"): m.group("body").strip() for m in _SECTION_RE.finditer(text)}


class PlanWatcher(QObject):
    qt_plan_changed = Signal(dict)   # nowe sekcje planu
    qt_plan_error = Signal(str)      # błąd odczytu

    POLL_INTERVAL_MS = 60_000

    def __init__(self, plan_path: Path | str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._plan_path = Path(plan_path)
        self._last_text: str | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._poll()
        self._timer.start()
        logger.debug("PlanWatcher started: %s", self._plan_path)

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        try:
            text = self._plan_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("PlanWatcher read error: %s", exc)
            self.qt_plan_error.emit(str(exc))
            return

        if text != self._last_text:
            self._last_text = text
            sections = _parse_plan(text)
            logger.debug("PLAN.md zmieniony, sekcje: %s", list(sections.keys()))
            self.qt_plan_changed.emit(sections)
