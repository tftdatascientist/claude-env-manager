from __future__ import annotations

import logging
import os
from datetime import date, datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from razd.db.repository import RazdRepository
from razd.notion.exporter import RazdNotionExporter

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_MIN = 15


class RazdNotionSyncWorker(QObject):
    """Cyklicznie synchronizuje aktywności z SQLite do Notion.

    Uruchamiany w osobnym QThread. Interwał pobierany z env RAZD_NOTION_SYNC_INTERVAL_MIN
    lub przekazywany przez konstruktor.
    """

    sync_done = Signal(str)   # emituje datę (YYYY-MM-DD) po udanym syncу
    sync_error = Signal(str)  # emituje komunikat błędu

    def __init__(
        self,
        repo: RazdRepository,
        interval_mins: int | None = None,
        export_urls: bool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._interval_mins = interval_mins or _parse_interval_env()
        self._export_urls = export_urls if export_urls is not None else _parse_export_urls_env()
        self._exporter: RazdNotionExporter | None = None
        self._timer: QTimer | None = None

    # --- public API ---

    def start(self) -> None:
        """Startuje timer i od razu odpala pierwszy sync."""
        self._exporter = RazdNotionExporter(
            repo=self._repo,
            export_urls=self._export_urls,
        )
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_mins * 60 * 1000)
        self._timer.timeout.connect(self._run_sync)
        self._timer.start()
        self._run_sync()

    def stop(self) -> None:
        if self._timer:
            self._timer.stop()

    # --- private ---

    def _run_sync(self) -> None:
        today = date.today()
        logger.debug("RAZD Notion sync: start dla %s", today)
        try:
            page_id = self._exporter.export_session(today)  # type: ignore[union-attr]
            if page_id:
                self.sync_done.emit(today.isoformat())
        except Exception as exc:
            msg = f"Notion sync error: {exc}"
            logger.error(msg)
            self.sync_error.emit(msg)


class RazdNotionSyncThread(QThread):
    """QThread owning RazdNotionSyncWorker — gotowy do użycia z main_window."""

    sync_done = Signal(str)
    sync_error = Signal(str)

    def __init__(
        self,
        repo: RazdRepository,
        interval_mins: int | None = None,
        export_urls: bool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._interval_mins = interval_mins
        self._export_urls = export_urls
        self._worker: RazdNotionSyncWorker | None = None

    def run(self) -> None:
        self._worker = RazdNotionSyncWorker(
            repo=self._repo,
            interval_mins=self._interval_mins,
            export_urls=self._export_urls,
        )
        self._worker.sync_done.connect(self.sync_done)
        self._worker.sync_error.connect(self.sync_error)
        self._worker.start()
        self.exec()  # Qt event loop wewnątrz wątku

    def stop_worker(self) -> None:
        if self._worker:
            self._worker.stop()
        self.quit()
        self.wait(3000)


# --- helpers ---

def _parse_interval_env() -> int:
    try:
        return int(os.environ.get("RAZD_NOTION_SYNC_INTERVAL_MIN", _DEFAULT_INTERVAL_MIN))
    except ValueError:
        return _DEFAULT_INTERVAL_MIN


def _parse_export_urls_env() -> bool:
    return os.environ.get("RAZD_NOTION_EXPORT_URLS", "false").lower() == "true"
