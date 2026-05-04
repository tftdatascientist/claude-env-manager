"""Scanner 2 poziomów hooków CC: global + project."""

from __future__ import annotations

from pathlib import Path

from src.hooker.core.model import Hook, HookLevel
from src.hooker.core.parser import parse_settings


GLOBAL_SETTINGS = Path.home() / ".claude" / "settings.json"


def scan_global() -> tuple[list[Hook], Path]:
    """Zwraca (hooki, ścieżka_pliku) z globalnych ustawień CC."""
    hooks = parse_settings(GLOBAL_SETTINGS, HookLevel.GLOBAL)
    return hooks, GLOBAL_SETTINGS


def scan_project(project_path: Path) -> tuple[list[Hook], list[Path]]:
    """Zwraca (hooki, lista_plików) z ustawień projektu.

    Łączy hooks z .claude/settings.json i .claude/settings.local.json.
    Każdy plik parsowany niezależnie — merge logic w merger.py.
    """
    claude_dir = project_path / ".claude"

    candidates = [
        claude_dir / "settings.json",
        claude_dir / "settings.local.json",
    ]

    hooks: list[Hook] = []
    found_files: list[Path] = []

    for p in candidates:
        parsed = parse_settings(p, HookLevel.PROJECT)
        if parsed or p.exists():
            hooks.extend(parsed)
            if p.exists():
                found_files.append(p)

    return hooks, found_files


def scan_empty_candidates(project_path: Path | None = None) -> list[Path]:
    """Zwraca listę plików JSON gdzie można zapisać hooki ale aktualnie nie ma tam żadnych.

    Używane przez Hook Finder do sekcji 'Pliki bez hooków'.
    """
    candidates: list[Path] = []

    # Global: jeśli plik istnieje ale nie ma sekcji hooks
    if GLOBAL_SETTINGS.exists():
        from src.hooker.core.parser import parse_settings_raw
        data = parse_settings_raw(GLOBAL_SETTINGS)
        if data is not None and not data.get("hooks"):
            candidates.append(GLOBAL_SETTINGS)

    # Project: pliki które mogłyby istnieć ale ich nie ma (lub istnieją bez hooków)
    if project_path is not None:
        claude_dir = project_path / ".claude"
        for name in ("settings.json", "settings.local.json"):
            p = claude_dir / name
            if not p.exists():
                candidates.append(p)
            else:
                from src.hooker.core.parser import parse_settings_raw
                data = parse_settings_raw(p)
                if data is not None and not data.get("hooks"):
                    candidates.append(p)

    return candidates
