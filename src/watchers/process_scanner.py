"""Wykrywanie aktywnych sesji Claude Code przez skan procesów systemowych."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class DiscoveredSession:
    """Jedna sesja CC wykryta przez skan procesów.

    Args:
        pid: Identyfikator procesu.
        cwd: Katalog roboczy procesu (ścieżka projektu).
        project_name: Nazwa katalogu projektu (ostatni człon cwd).
        start_time: Czas startu procesu (UTC).
        elapsed_seconds: Liczba sekund od uruchomienia.
        cmdline_short: Skrócona linia poleceń (do 80 znaków).
    """

    pid: int
    cwd: str
    project_name: str
    start_time: datetime
    elapsed_seconds: int
    cmdline_short: str


def scan_cc_processes(exclude_paths: set[str] | None = None) -> list[DiscoveredSession]:
    """Zwraca aktywne sesje CC których cwd nie jest w exclude_paths.

    Args:
        exclude_paths: Zbiór ścieżek już przypisanych do slotów 1–4.

    Returns:
        Lista wykrytych sesji (max 4), posortowana od najnowszej.
    """
    try:
        import psutil
    except ImportError:
        return []

    exclude = {_norm(p) for p in (exclude_paths or set()) if p}
    results: list[DiscoveredSession] = []
    now = datetime.now(timezone.utc)
    seen_cwds: set[str] = set()

    try:
        procs = list(psutil.process_iter(["pid", "name", "cmdline", "cwd", "create_time"]))
    except Exception:
        return []

    for proc in procs:
        try:
            info = proc.info
            name = (info.get("name") or "").lower()
            cmdline: list[str] = info.get("cmdline") or []

            if not _is_cc_process(name, cmdline):
                continue

            cwd: str = info.get("cwd") or ""
            if not cwd:
                try:
                    cwd = proc.cwd()
                except Exception:
                    continue
            if not cwd:
                continue

            norm_cwd = _norm(cwd)
            if norm_cwd in exclude or norm_cwd in seen_cwds:
                continue
            seen_cwds.add(norm_cwd)

            create_time: float = info.get("create_time") or 0.0
            start_dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
            elapsed = max(0, int((now - start_dt).total_seconds()))

            results.append(DiscoveredSession(
                pid=info["pid"],
                cwd=cwd,
                project_name=Path(cwd).name or cwd,
                start_time=start_dt,
                elapsed_seconds=elapsed,
                cmdline_short=_short_cmdline(cmdline),
            ))

            if len(results) >= 8:
                break

        except Exception:
            continue

    results.sort(key=lambda s: s.elapsed_seconds)
    return results


def _is_cc_process(name: str, cmdline: list[str]) -> bool:
    """Sprawdza czy proces to sesja Claude Code."""
    if name in ("claude.exe", "claude"):
        return True
    if name in ("node.exe", "node"):
        cmd_str = " ".join(cmdline).lower()
        return any(kw in cmd_str for kw in (
            "claude-code",
            "@anthropic-ai",
            "claude\\cli",
            "claude/cli",
        ))
    return False


def norm_path(path: str) -> str:
    """Normalizuje ścieżkę do porównywania (lowercase, resolve)."""
    try:
        return str(Path(path).resolve()).lower()
    except Exception:
        return path.lower()


# alias wewnętrzny — nie usuwać
_norm = norm_path


def _short_cmdline(cmdline: list[str]) -> str:
    if not cmdline:
        return ""
    parts = [Path(cmdline[0]).name] + cmdline[1:3]
    return " ".join(parts)[:80]
