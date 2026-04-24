"""Statystyki projektu: rozmiary plików, struktura, informacje Git."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

KEY_FILES = [
    "CLAUDE.md",
    "PLAN.md",
    "ARCHITECTURE.md",
    "CONVENTIONS.md",
    "STATUS.md",
    "CHANGELOG.md",
]

_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "dist", "build", ".next", ".nuxt", ".cache", "coverage",
    ".pytest_cache", ".mypy_cache", "out",
}


@dataclass
class ProjectStats:
    """Statystyki projektu odczytane z systemu plików i Git.

    Args:
        file_count: Liczba plików (bez katalogów ukrytych/build).
        folder_count: Liczba folderów (bez ukrytych).
        disk_usage_bytes: Łączny rozmiar wszystkich plików w bajtach.
        key_file_sizes: Słownik {nazwa_pliku: rozmiar_w_bajtach} dla kluczowych plików.
        has_git: True jeśli katalog zawiera repozytorium Git.
        git_remote_url: URL zdalnego repozytorium (origin) lub "".
        git_branch: Aktualna gałąź lub "".
        error: Komunikat błędu jeśli skanowanie się nie powiodło.
    """

    file_count: int = 0
    folder_count: int = 0
    disk_usage_bytes: int = 0
    key_file_sizes: dict[str, int] = field(default_factory=dict)
    has_git: bool = False
    git_remote_url: str = ""
    git_branch: str = ""
    error: str = ""


def get_project_stats(project_path: str) -> ProjectStats:
    """Zbiera statystyki projektu z systemu plików i Git.

    Args:
        project_path: Ścieżka do katalogu projektu.

    Returns:
        ProjectStats lub stats z wypełnionym polem error.
    """
    root = Path(project_path)
    if not root.is_dir():
        return ProjectStats(error=f"Katalog nie istnieje: {project_path}")

    stats = ProjectStats()

    # Rozmiary kluczowych plików
    for name in KEY_FILES:
        p = root / name
        if p.is_file():
            try:
                stats.key_file_sizes[name] = p.stat().st_size
            except OSError:
                pass

    # Skanowanie struktury katalogów
    try:
        for entry in _walk(root):
            if entry.is_file(follow_symlinks=False):
                stats.file_count += 1
                try:
                    stats.disk_usage_bytes += entry.stat().st_size
                except OSError:
                    pass
            elif entry.is_dir(follow_symlinks=False):
                stats.folder_count += 1
    except OSError as e:
        stats.error = str(e)

    # Informacje Git
    git_dir = root / ".git"
    if git_dir.is_dir():
        stats.has_git = True
        stats.git_remote_url = _git_remote_url(root)
        stats.git_branch = _git_branch(root)

    return stats


def _walk(root: Path):
    """Generator plików i folderów z pominięciem katalogów build/cache."""
    try:
        for entry in os.scandir(root):
            if entry.name.startswith(".") and entry.name not in (".git",):
                continue
            if entry.is_dir(follow_symlinks=False):
                if entry.name in _SKIP_DIRS:
                    continue
                yield Path(entry.path)
                yield from _walk(Path(entry.path))
            else:
                yield Path(entry.path)
    except PermissionError:
        pass


def _git_remote_url(root: Path) -> str:
    """Odczytuje URL zdalnego repozytorium origin z .git/config."""
    config_path = root / ".git" / "config"
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    in_origin = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == '[remote "origin"]':
            in_origin = True
            continue
        if in_origin:
            if stripped.startswith("["):
                break
            if stripped.startswith("url ="):
                return stripped.split("=", 1)[1].strip()
    return ""


def _git_branch(root: Path) -> str:
    """Odczytuje aktualną gałąź z .git/HEAD."""
    head_path = root / ".git" / "HEAD"
    try:
        text = head_path.read_text(encoding="utf-8").strip()
        if text.startswith("ref: refs/heads/"):
            return text[len("ref: refs/heads/"):]
        return text[:8]  # detached HEAD — skrócony hash
    except OSError:
        return ""


def fmt_size(size_bytes: int) -> str:
    """Formatuje rozmiar w bajtach jako czytelny string.

    Args:
        size_bytes: Rozmiar w bajtach.

    Returns:
        String w formacie "1.2 MB", "345 KB", "89 B".
    """
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1_024:
        return f"{size_bytes / 1_024:.1f} KB"
    return f"{size_bytes} B"
