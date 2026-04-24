"""Uruchamianie sesji VS Code + cc-panel terminali dla projektów CC."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

_USTAWIENIA_PATH = Path.home() / ".claude" / "cc-panel" / "ustawienia.json"
_LAUNCH_REQUEST_PATH = Path.home() / ".claude" / "cc-panel" / "launch-request.json"


# ------------------------------------------------------------------ #
# Pomocnicze                                                            #
# ------------------------------------------------------------------ #

def _run_code(*args: str) -> bool:
    try:
        subprocess.Popen(["cmd", "/c", "code", *args])
        return True
    except OSError:
        return False


def _update_ustawienia_path(slot_id: int, project_path: str) -> None:
    try:
        if _USTAWIENIA_PATH.exists():
            data = json.loads(_USTAWIENIA_PATH.read_text(encoding="utf-8"))
        else:
            data = {}
        paths: list[str] = data.get("projectPaths", ["", "", "", ""])
        while len(paths) < 4:
            paths.append("")
        paths[slot_id - 1] = project_path
        data["projectPaths"] = paths
        _USTAWIENIA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USTAWIENIA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError):
        pass


def _write_launch_request(
    slot_id: int,
    project_path: str,
    terminal_count: int,
    vibe_prompt: str,
) -> None:
    payload = {
        "slotId": slot_id,
        "projectPath": project_path,
        "terminalCount": max(1, min(4, terminal_count)),
        "vibePrompt": vibe_prompt,
    }
    _LAUNCH_REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LAUNCH_REQUEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ------------------------------------------------------------------ #
# Publiczne API                                                         #
# ------------------------------------------------------------------ #

def prepare_and_launch(
    slot_id: int,
    project_path: str,
    terminal_count: int = 1,
    vibe_prompt: str = "",
) -> bool:
    """Zapisuje konfigurację slotu i uruchamia VS Code z cc-panel.

    VS Code aktywuje ccPanel.launchSlot który odczyta launch-request.json
    i sam otworzy panel + terminale + wklei prompt po załadowaniu CC.
    """
    if not project_path or not Path(project_path).is_dir():
        return False
    _update_ustawienia_path(slot_id, project_path)
    _write_launch_request(slot_id, project_path, terminal_count, vibe_prompt)
    return _run_code(project_path, "--command", "ccPanel.launchSlot")


def open_vscode_window(project_path: str) -> bool:
    """Otwiera nowe okno VS Code z projektem (funkcja OKNO)."""
    if project_path and Path(project_path).is_dir():
        return _run_code("--new-window", project_path)
    return _run_code("--new-window")


def terminate_vscode_session(slot_id: int) -> bool:
    """Zatrzymuje sesję Auto-Accept CC dla danego slotu."""
    return _run_code("--command", "ccPanel.stopAutoAccept")


def build_cc_command(model: str, effort: str, permission_flag: str) -> str:
    """Buduje komendę CC CLI (informacyjnie / do wklejenia w terminalu)."""
    parts = ["claude"]
    if permission_flag:
        parts.append(permission_flag)
    if model:
        parts.extend(["--model", model])
    return " ".join(parts)
