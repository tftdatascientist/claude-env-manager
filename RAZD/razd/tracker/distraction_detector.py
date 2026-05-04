from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from razd.tracker.poller import EventDTO

WINDOW_S = 60.0          # szerokość okna sliding window
DEFAULT_THRESHOLD = 6.0  # przełączeń/min powyżej którego alert
ALERT_CONSECUTIVE = 3    # liczba kolejnych pomiarów powyżej progu → alert


class RazdDistractionDetector(QObject):
    """
    Monitoruje context-switching (zmiany aktywnej apki).
    Emituje distraction_alert gdy switches/min > threshold przez ALERT_CONSECUTIVE pomiary.
    Emituje score_updated przy każdym pomiarze.
    """

    distraction_alert = Signal(float)   # switches_per_min
    score_updated = Signal(float)       # switches_per_min (każdy poll)

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.threshold = threshold
        self._switch_times: deque[float] = deque()
        self._last_process: str | None = None
        self._above_threshold_count: int = 0
        self._alerted: bool = False

    def feed(self, dto: EventDTO) -> None:
        """Przyjmuje EventDTO i aktualizuje licznik przełączeń."""
        now = time.monotonic()

        # wykryj przełączenie apki (ignoruj pierwsze wejście i zdarzenia idle)
        proc = dto.process_name
        if proc and dto.event_type != "idle":
            if self._last_process is not None and proc != self._last_process:
                self._switch_times.append(now)
            self._last_process = proc

        # oczyść stare zdarzenia poza oknem
        cutoff = now - WINDOW_S
        while self._switch_times and self._switch_times[0] < cutoff:
            self._switch_times.popleft()

        # oblicz bieżące switches/min
        spm = len(self._switch_times) / (WINDOW_S / 60.0)
        self.score_updated.emit(spm)

        if spm > self.threshold:
            self._above_threshold_count += 1
            if self._above_threshold_count >= ALERT_CONSECUTIVE and not self._alerted:
                self._alerted = True
                self.distraction_alert.emit(spm)
        else:
            self._above_threshold_count = 0
            self._alerted = False

    def reset(self) -> None:
        self._switch_times.clear()
        self._last_process = None
        self._above_threshold_count = 0
        self._alerted = False

    @property
    def current_spm(self) -> float:
        now = time.monotonic()
        cutoff = now - WINDOW_S
        count = sum(1 for t in self._switch_times if t >= cutoff)
        return count / (WINDOW_S / 60.0)
