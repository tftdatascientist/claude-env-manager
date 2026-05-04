"""jsonl_watcher.py — watchdog na SSS.jsonl, tail-by-offset, emituje Qt signal."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QTimer


class JsonlWatcher(QObject):
    """Śledzi plik SSS.jsonl i emituje new_event dla każdej nowej linii."""

    new_event = Signal(dict)  # emitowany dla każdego nowego eventu
    file_changed = Signal()   # emitowany gdy plik się zmienił (do odświeżenia snapshot)

    def __init__(self, jsonl_path: Path, poll_interval_ms: int = 500, parent=None) -> None:
        super().__init__(parent)
        self._path = jsonl_path
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        """Rozpoczyna śledzenie — najpierw czyta istniejące linie do offsetu."""
        if self._path.exists():
            self._offset = self._path.stat().st_size
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        if not self._path.exists():
            return
        try:
            size = self._path.stat().st_size
        except OSError:
            return
        if size <= self._offset:
            return

        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                f.seek(self._offset)
                new_data = f.read()
                self._offset = f.tell()
        except OSError:
            return

        changed = False
        for line in new_data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                self.new_event.emit(ev)
                changed = True
            except json.JSONDecodeError:
                pass

        if changed:
            self.file_changed.emit()

    def reset_to_start(self) -> None:
        """Resetuje offset do 0 — przydatne przy pełnym fold od początku."""
        self._offset = 0
