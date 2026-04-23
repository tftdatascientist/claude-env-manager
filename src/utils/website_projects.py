"""Persistence for website-marked projects displayed in the Websites tab."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "website_projects.json"


def load_website_projects() -> list[str]:
    """Load list of website project paths."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_website_projects(projects: list[str]) -> None:
    """Save full list of website project paths."""
    _CONFIG_PATH.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


def add_website_project(path: str) -> None:
    """Add a project path to website list (if not already present)."""
    projects = load_website_projects()
    if path not in projects:
        projects.append(path)
        save_website_projects(projects)


def remove_website_project(path: str) -> None:
    """Remove a project path from website list."""
    projects = load_website_projects()
    if path in projects:
        projects.remove(path)
        save_website_projects(projects)


def is_website_project(path: str) -> bool:
    """Check if a project path is in the website list."""
    return path in load_website_projects()
