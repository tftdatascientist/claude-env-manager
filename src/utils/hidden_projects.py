"""Persistence for hidden projects filtered out from History."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "hidden_projects.json"


def load_hidden_projects() -> list[str]:
    """Load list of hidden project paths."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_hidden_projects(projects: list[str]) -> None:
    """Save full list of hidden project paths."""
    _CONFIG_PATH.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


def add_hidden_project(path: str) -> None:
    """Add a project path to hidden list."""
    projects = load_hidden_projects()
    if path not in projects:
        projects.append(path)
        save_hidden_projects(projects)


def remove_hidden_project(path: str) -> None:
    """Remove a project path from hidden list (unhide)."""
    projects = load_hidden_projects()
    if path in projects:
        projects.remove(path)
        save_hidden_projects(projects)


def is_hidden_project(path: str) -> bool:
    """Check if a project path is hidden."""
    return path in load_hidden_projects()
