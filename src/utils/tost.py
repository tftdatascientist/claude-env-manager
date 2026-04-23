"""TOST (Token Optimization System Tool) launcher and integration utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

# TOST project directory
TOST_PROJECT_DIR = (
    Path.home() / "Documents" / ".MD" / "PARA" / "SER"
    / "10_PROJEKTY" / "SIDE" / "PRAWY"
)


def tost_project_dir() -> Path:
    """Return the TOST project directory."""
    return TOST_PROJECT_DIR


def is_tost_installed() -> bool:
    """Check if TOST project directory exists and has expected files."""
    return (TOST_PROJECT_DIR / "tost").is_dir()


def _run_tost_in_powershell(command: str, title: str, color: str = "Cyan") -> subprocess.Popen | None:
    """Launch a TOST command in a new PowerShell window.

    Returns the Popen object, or None on error.
    """
    project_dir = str(TOST_PROJECT_DIR)
    ps_command = (
        f"Set-Location '{project_dir}'; "
        f"$Host.UI.RawUI.WindowTitle = 'TOST - {title}'; "
        f"Write-Host '=== TOST {title} ===' -ForegroundColor {color}; "
        f"python -m tost {command}"
    )
    try:
        return subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", ps_command],
            cwd=project_dir,
        )
    except OSError:
        return None


def launch_monitor() -> subprocess.Popen | None:
    """Launch TOST monitor (live dashboard + OTLP collector)."""
    return _run_tost_in_powershell("", "Monitor", "Cyan")


def launch_duel() -> subprocess.Popen | None:
    """Launch TOST duel mode (profile comparison)."""
    return _run_tost_in_powershell("duel", "Duel", "Yellow")


def launch_sim() -> subprocess.Popen | None:
    """Launch TOST simulator (cost simulation)."""
    return _run_tost_in_powershell("sim", "Simulator", "Green")


def launch_train() -> subprocess.Popen | None:
    """Launch TOST trainer (context engineering)."""
    return _run_tost_in_powershell("train", "Trainer", "Magenta")


def launch_notion_sync(once: bool = False) -> subprocess.Popen | None:
    """Launch TOST Notion sync in a new PowerShell window.

    Loads .env from TOST project dir for NOTION_TOKEN and NOTION_DATABASE_ID.
    """
    project_dir = str(TOST_PROJECT_DIR)
    sync_cmd = "sync --once -v" if once else "sync -v"

    # Build PowerShell that loads .env then runs sync
    ps_lines = [
        f"Set-Location '{project_dir}'",
        f"$Host.UI.RawUI.WindowTitle = 'TOST - Notion Sync'",
        # Load .env
        f"$envFile = Join-Path '{project_dir}' '.env'",
        "if (Test-Path $envFile) {"
        "  Get-Content $envFile | ForEach-Object {"
        "    $line = $_.Trim();"
        "    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {"
        "      $parts = $line -split '=', 2;"
        "      [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())"
        "    }"
        "  };"
        "  Write-Host 'Loaded .env' -ForegroundColor DarkGray"
        "} else {"
        "  Write-Host 'Warning: .env not found' -ForegroundColor Red"
        "}",
    ]
    if once:
        ps_lines.append("Write-Host '=== Notion Sync - single pass ===' -ForegroundColor Yellow")
    else:
        ps_lines.append("Write-Host '=== Notion Sync - continuous ===' -ForegroundColor Cyan")
    ps_lines.append(f"python -m tost {sync_cmd}")

    ps_command = "; ".join(ps_lines)
    try:
        return subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", ps_command],
            cwd=project_dir,
        )
    except OSError:
        return None
