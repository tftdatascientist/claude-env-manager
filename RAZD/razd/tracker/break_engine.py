from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from razd.tracker.poller import EventDTO

IDLE_RESET_S = 300.0   # 5 min idle = reset licznika pracy
DEFAULT_WORK_INTERVAL_MIN = 50


class RazdBreakEngine(QObject):
    """
    Śledzi ciągły czas pracy. Gdy przekroczy work_interval_min, emituje break_due.
    Reset następuje przy idle > IDLE_RESET_S lub po ręcznym wywołaniu take_break().
    """

    break_due = Signal(int)   # minuty przepracowane bez przerwy

    def __init__(
        self,
        work_interval_min: int = DEFAULT_WORK_INTERVAL_MIN,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.work_interval_min = work_interval_min
        self._active_seconds: float = 0.0
        self._alerted: bool = False

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def feed(self, dto: EventDTO) -> None:
        """Przyjmuje EventDTO z pollera i aktualizuje licznik pracy."""
        if dto.event_type == "idle" and dto.idle_seconds >= IDLE_RESET_S:
            self._reset()
            return

        if dto.event_type != "idle":
            self._active_seconds += 2.0   # każdy poll = 2s aktywności
            self._check_threshold()

    def take_break(self) -> int:
        """Ręczne potwierdzenie przerwy. Zwraca minuty przepracowane i resetuje."""
        minutes = int(self._active_seconds / 60)
        self._reset()
        return minutes

    @property
    def worked_seconds(self) -> float:
        return self._active_seconds

    @property
    def worked_minutes(self) -> int:
        return int(self._active_seconds / 60)

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _check_threshold(self) -> None:
        if not self._alerted and self._active_seconds >= self.work_interval_min * 60:
            self._alerted = True
            self.break_due.emit(self.worked_minutes)

    def _reset(self) -> None:
        self._active_seconds = 0.0
        self._alerted = False
