"""Category color configuration for the tree panel."""

from __future__ import annotations

import json
from pathlib import Path

# Default colors for tree categories (VS Code-inspired)
DEFAULT_COLORS: dict[str, str] = {
    "Managed (read-only)": "#e06c75",   # red - restricted
    "User": "#c678dd",                   # purple - personal
    "Projects": "#61afef",               # blue - projects
    "External": "#98c379",               # green - external
    "Rules/": "#d19a66",                 # orange
    "Skills/": "#56b6c2",               # cyan
    "Agents/": "#e5c07b",              # yellow
    "Memory/": "#c678dd",               # purple
    "SSH keys/": "#98c379",             # green
    "Environment variables": "#d19a66",  # orange
}

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "colors_config.json"


def load_colors() -> dict[str, str]:
    """Load category colors, merging saved with defaults."""
    colors = dict(DEFAULT_COLORS)
    if _CONFIG_PATH.exists():
        try:
            saved = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            colors.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return colors


def save_color(category: str, hex_color: str) -> None:
    """Save a single category color to config."""
    saved: dict[str, str] = {}
    if _CONFIG_PATH.exists():
        try:
            saved = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    saved[category] = hex_color
    _CONFIG_PATH.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")


def reset_colors() -> None:
    """Remove saved colors, reverting to defaults."""
    if _CONFIG_PATH.exists():
        _CONFIG_PATH.unlink()
