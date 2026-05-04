from __future__ import annotations

import sys
import winreg
from pathlib import Path

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "RAZD"


def _build_command() -> str:
    """Buduje komendę startową — pythonw.exe (bez konsoli) + ścieżka main.py."""
    python_exe = Path(sys.executable)
    # pythonw.exe jest obok python.exe w tym samym katalogu
    pythonw = python_exe.parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = python_exe  # fallback na python.exe

    main_py = Path(__file__).parent.parent / "main.py"
    return f'"{pythonw}" "{main_py}" --minimized'


def is_enabled() -> bool:
    """Zwraca True jeśli RAZD jest zarejestrowany w autostarcie Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except OSError:
        return False


def enable() -> None:
    """Dodaje RAZD do autostartu Windows (HKCU Run)."""
    cmd = _build_command()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, cmd)


def disable() -> None:
    """Usuwa RAZD z autostartu Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _APP_NAME)
    except OSError:
        pass
