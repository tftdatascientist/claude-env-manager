"""Audit logger dla Hookera — rotujący logfile z hash before/after każdego zapisu."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_LOG_PATH = Path.home() / ".claude" / "hooker" / "hooker.log"
_MAX_LINES = 500


def _log_path() -> Path:
    return _LOG_PATH


def log_write(
    target: Path,
    hash_before: str,
    hash_after: str,
    backup: Path | None = None,
) -> None:
    """Zapisuje wpis o edycji pliku do logu."""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": "write",
        "file": str(target),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup": str(backup) if backup else None,
    }
    _append(entry)


def log_restore(target: Path, backup: Path) -> None:
    """Zapisuje wpis o restore z backupu."""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": "restore",
        "file": str(target),
        "backup": str(backup),
    }
    _append(entry)


def log_error(target: Path, error: str) -> None:
    """Zapisuje wpis o błędzie przy operacji na pliku."""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": "error",
        "file": str(target),
        "error": error,
    }
    _append(entry)


def read_log(n: int = 50) -> list[dict]:
    """Zwraca ostatnie n wpisów (od najnowszego)."""
    log = _log_path()
    if not log.exists():
        return []
    lines = log.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= n:
            break
    return entries


def _append(entry: dict) -> None:
    log = _log_path()
    log.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(entry, ensure_ascii=False) + "\n"

    # Rotacja: jeśli przekroczono MAX_LINES, przytnij do połowy
    if log.exists():
        existing = log.read_text(encoding="utf-8")
        lines = existing.splitlines(keepends=True)
        if len(lines) >= _MAX_LINES:
            lines = lines[len(lines) // 2:]
            log.write_text("".join(lines), encoding="utf-8")

    with log.open("a", encoding="utf-8") as f:
        f.write(line)
