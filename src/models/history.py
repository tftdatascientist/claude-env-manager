"""History model for Claude Code prompt history."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class HistoryEntry:
    display: str
    timestamp: int
    project: str
    session_id: str
    pasted_contents: dict = field(default_factory=dict)

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def project_name(self) -> str:
        return Path(self.project).name if self.project else "(unknown)"

    @property
    def time_str(self) -> str:
        return self.datetime.strftime("%Y-%m-%d %H:%M")

    @property
    def short_display(self) -> str:
        text = self.display.replace("\n", " ").strip()
        if len(text) > 120:
            return text[:117] + "..."
        return text


def load_history(path: Path) -> list[HistoryEntry]:
    """Load history entries from a .jsonl file. Returns newest first."""
    entries: list[HistoryEntry] = []
    if not path.exists():
        return entries
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return entries

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            entries.append(HistoryEntry(
                display=data.get("display", ""),
                timestamp=data.get("timestamp", 0),
                project=data.get("project", ""),
                session_id=data.get("sessionId", ""),
                pasted_contents=data.get("pastedContents", {}),
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries
