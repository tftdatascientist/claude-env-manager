"""Project display name aliases."""

from __future__ import annotations

import json
from pathlib import Path

_ALIASES_PATH = Path(__file__).resolve().parent.parent.parent / "aliases.json"


def load_aliases() -> dict[str, str]:
    """Load project aliases (key = project root path, value = display name)."""
    if _ALIASES_PATH.exists():
        try:
            return json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_alias(project_path: str, display_name: str) -> None:
    """Save a display name alias for a project."""
    aliases = load_aliases()
    aliases[project_path] = display_name
    _ALIASES_PATH.write_text(json.dumps(aliases, indent=2, ensure_ascii=False), encoding="utf-8")


def remove_alias(project_path: str) -> None:
    """Remove a display name alias, reverting to original folder name."""
    aliases = load_aliases()
    if project_path in aliases:
        del aliases[project_path]
        _ALIASES_PATH.write_text(json.dumps(aliases, indent=2, ensure_ascii=False), encoding="utf-8")
