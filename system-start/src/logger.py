"""
Centralny logger PCC — zapisuje do logs/pcc.log i na stderr.
Użycie: get_logger(__name__)
"""
from __future__ import annotations

import logging
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "pcc.log"
_MAX_BYTES = 500_000  # ~500 KB, potem rotate
_BACKUP_COUNT = 3


def get_logger(name: str = "pcc") -> logging.Logger:
    """Zwraca logger z handlerem do pliku logs/pcc.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    LOG_PATH.parent.mkdir(exist_ok=True)

    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(
        LOG_PATH,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)
    return logger
