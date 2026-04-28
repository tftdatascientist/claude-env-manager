from __future__ import annotations

import ctypes
import ctypes.wintypes


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    """Zwraca liczbę sekund od ostatniej aktywności użytkownika (mysz/klawiatura)."""
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    tick_now = ctypes.windll.kernel32.GetTickCount()
    elapsed_ms = tick_now - info.dwTime
    return elapsed_ms / 1000.0
