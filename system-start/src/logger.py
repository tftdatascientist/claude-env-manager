"""
Centralny logger PCC.
- Plik: logs/pcc.log (RotatingFileHandler)
- Notion: każdy wpis INFO+ trafia jako rekord do bazy PCC_Logs

Użycie: get_logger(__name__)
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LOG_PATH = BASE_DIR / "logs" / "pcc.log"
_MAX_BYTES = 500_000
_BACKUP_COUNT = 3

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
NOTION_LOGS_DB = os.environ.get("NOTION_LOGS_DB", "")

# Nazwa projektu = nazwa katalogu (np. "system-start")
_PROJECT_NAME = BASE_DIR.name


class NotionLogHandler(logging.Handler):
    """
    Handler zapisujący wpisy logów do bazy PCC_Logs w Notion.
    Działa asynchronicznie — nie blokuje wywołującego kodu.
    Poziom minimalny: INFO (DEBUG jest pomijane).
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self._queue: queue.Queue[logging.LogRecord | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        self._queue.put_nowait(record)

    def _worker(self) -> None:
        while True:
            record = self._queue.get()
            if record is None:
                break
            try:
                self._send(record)
            except Exception:
                pass  # nigdy nie przerywaj pracy przez błąd Notion

    def _send(self, record: logging.LogRecord) -> None:
        from notion_client import Client
        client = Client(auth=NOTION_TOKEN)

        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        level = record.levelname
        message = record.getMessage()[:2000]
        module = record.name[:100]

        # Próba z pełnymi właściwościami (wymagają ręcznie dodanych kolumn w Notion)
        try:
            client.pages.create(
                parent={"type": "database_id", "database_id": NOTION_LOGS_DB},
                properties={
                    "Name":      {"title": [{"type": "text", "text": {"content": message}}]},
                    "Level":     {"select": {"name": level}},
                    "Module":    {"rich_text": [{"type": "text", "text": {"content": module}}]},
                    "Project":   {"rich_text": [{"type": "text", "text": {"content": _PROJECT_NAME}}]},
                    "Timestamp": {"date": {"start": ts}},
                },
            )
        except Exception:
            # Fallback: wszystko w Name — działa nawet bez dodatkowych kolumn
            packed = f"[{level}] {ts[:19]} | {module} | {message}"[:2000]
            client.pages.create(
                parent={"type": "database_id", "database_id": NOTION_LOGS_DB},
                properties={
                    "Name": {"title": [{"type": "text", "text": {"content": packed}}]},
                },
            )

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=5)
        super().close()


def get_logger(name: str = "pcc") -> logging.Logger:
    """Zwraca logger z handlerem do pliku i (jeśli skonfigurowano) do Notion."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    LOG_PATH.parent.mkdir(exist_ok=True)

    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(
        LOG_PATH, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    if NOTION_TOKEN and NOTION_LOGS_DB:
        logger.addHandler(NotionLogHandler())

    logger.setLevel(logging.DEBUG)
    return logger
