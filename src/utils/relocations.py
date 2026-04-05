"""Persistent mapping of old project paths to their new locations."""

import json
from pathlib import Path

_RELOCATIONS_FILE = Path(__file__).parent.parent.parent / "relocations.json"


def load_relocations() -> dict[str, str]:
    """Load old_path -> new_path mapping."""
    if not _RELOCATIONS_FILE.exists():
        return {}
    try:
        data = json.loads(_RELOCATIONS_FILE.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


def save_relocation(old_path: str, new_path: str) -> None:
    """Add or update a relocation mapping."""
    relocations = load_relocations()
    relocations[old_path] = new_path
    _save(relocations)


def remove_relocation(old_path: str) -> None:
    """Remove a relocation mapping."""
    relocations = load_relocations()
    relocations.pop(old_path, None)
    _save(relocations)


def resolve_path(original_path: str) -> tuple[str, bool]:
    """Resolve a project path through relocations.

    Returns (resolved_path, was_relocated).
    """
    relocations = load_relocations()
    if original_path in relocations:
        return relocations[original_path], True
    return original_path, False


def _save(relocations: dict[str, str]) -> None:
    _RELOCATIONS_FILE.write_text(
        json.dumps(relocations, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
