"""Persistence for active (pinned) projects displayed in the Active Projects tab."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "active_projects.json"


def load_active_projects() -> list[str]:
    """Load list of active project paths."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_active_projects(projects: list[str]) -> None:
    """Save full list of active project paths."""
    _CONFIG_PATH.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


def add_active_project(path: str) -> None:
    """Add a project path to active list (if not already present)."""
    projects = load_active_projects()
    if path not in projects:
        projects.append(path)
        save_active_projects(projects)


def remove_active_project(path: str) -> None:
    """Remove a project path from active list."""
    projects = load_active_projects()
    if path in projects:
        projects.remove(path)
        save_active_projects(projects)


def is_active_project(path: str) -> bool:
    """Check if a project path is in the active list."""
    return path in load_active_projects()
