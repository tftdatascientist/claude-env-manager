"""SSS Events API — produkuje eventy do <projekt>/.claude/SSS.jsonl."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

EVENTS_API_VERSION = 1

EventType = Literal[
    "session_start",
    "session_end",
    "script_run",
    "round_change",
    "buffer_add",
    "buffer_distribute",
    "task_done",
    "repo_finalized",
    "ps_imported",
]

RoundType = Literal["dev", "service"] | None


def project_id(project_path: Path) -> str:
    """sha1(absolutna_ścieżka_lowercase)[:12]."""
    abs_path = str(project_path.resolve()).lower()
    return hashlib.sha1(abs_path.encode()).hexdigest()[:12]


def _jsonl_path(project_path: Path) -> Path:
    return project_path.resolve() / ".claude" / "SSS.jsonl"


def append_event(
    project_path: Path,
    type: EventType,
    session_id: str,
    round: RoundType = None,
    payload: dict | None = None,
) -> dict:
    """Dopisuje jeden event do SSS.jsonl i zwraca go jako dict."""
    event = {
        "schema_version": EVENTS_API_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "type": type,
        "session_id": session_id,
        "project_id": project_id(project_path),
        "round": round,
        "payload": payload or {},
    }
    jsonl_file = _jsonl_path(project_path)
    jsonl_file.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def new_session_id() -> str:
    """Generuje nowy UUID4 do użycia jako session_id."""
    return str(uuid.uuid4())


def read_events(project_path: Path) -> list[dict]:
    """Wczytuje wszystkie eventy z SSS.jsonl, pomija uszkodzone linie."""
    jsonl_file = _jsonl_path(project_path)
    if not jsonl_file.exists():
        return []
    events = []
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events
