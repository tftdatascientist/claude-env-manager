from __future__ import annotations

from dataclasses import dataclass

import psutil
import win32gui
import win32process


@dataclass
class WindowInfo:
    process_name: str
    window_title: str
    pid: int


def get_active_window() -> WindowInfo | None:
    """Zwraca info o aktualnie aktywnym oknie lub None przy błędzie."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None

    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)

    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except psutil.NoSuchProcess:
        return None

    return WindowInfo(process_name=name, window_title=title, pid=pid)
