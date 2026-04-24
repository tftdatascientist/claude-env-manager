"""WMS (Web Management System) launcher utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

WMS_PROJECT_DIR = (
    Path.home() / "Documents" / ".MD" / "PARA" / "SER" / "CLAUDE CODE" / "WMS"
)

_PYTHONW = WMS_PROJECT_DIR / ".venv" / "Scripts" / "pythonw.exe"
_FLAGS = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP


def is_wms_installed() -> bool:
    """Check if WMS project directory and venv exist."""
    return _PYTHONW.is_file()


def launch_wms() -> subprocess.Popen | None:
    """Launch WMS main window (no specific panel)."""
    try:
        return subprocess.Popen(
            [str(_PYTHONW), "-m", "src"],
            cwd=str(WMS_PROJECT_DIR),
            creationflags=_FLAGS,
        )
    except OSError:
        return None


def launch_wms_panel(panel: str) -> subprocess.Popen | None:
    """Launch WMS and auto-open the given panel/dialog.

    Panel names: szablony, zakładki, portfolio, brief, etap1,
                 sync, audit, editor
    """
    try:
        return subprocess.Popen(
            [str(_PYTHONW), "-m", "src", "--open", panel],
            cwd=str(WMS_PROJECT_DIR),
            creationflags=_FLAGS,
        )
    except OSError:
        return None
