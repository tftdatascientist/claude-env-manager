from __future__ import annotations

import sys
import winreg
from pathlib import Path


def _find_desktop() -> Path:
    """Zwraca ścieżkę pulpitu z rejestru (obsługuje OneDrive Desktop)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            0,
            winreg.KEY_READ,
        ) as key:
            raw, _ = winreg.QueryValueEx(key, "Desktop")
            import os
            return Path(os.path.expandvars(raw))
    except OSError:
        return Path.home() / "Desktop"


def generate_icon() -> Path:
    """
    Rysuje ikonę RAZD (litera R, niebieski kwadrat) i zapisuje jako RAZD.ico
    obok main.py. Zwraca ścieżkę do pliku.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    output = Path(__file__).parent.parent / "RAZD.ico"

    px = QPixmap(256, 256)
    px.fill(QColor("#1565C0"))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Arial", 155, QFont.Weight.Bold))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "R")
    painter.end()

    if not px.save(str(output), "ICO"):
        # Qt ICO plugin może nie być dostępny — fallback na PNG
        output = output.with_suffix(".png")
        px.save(str(output), "PNG")

    return output


def create_shortcut() -> tuple[Path, str]:
    """
    Tworzy lub aktualizuje skrót RAZD.lnk na pulpicie Windows.
    Zwraca (ścieżka_skrótu, komunikat).
    """
    import win32com.client

    ico_path = generate_icon()
    main_py = Path(__file__).parent.parent / "main.py"

    python_exe = Path(sys.executable)
    pythonw = python_exe.parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = python_exe

    desktop = _find_desktop()
    shortcut_path = desktop / "RAZD.lnk"
    existed = shortcut_path.exists()

    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(shortcut_path))
    sc.TargetPath = str(pythonw)
    sc.Arguments = f'"{main_py}"'
    sc.WorkingDirectory = str(main_py.parent)
    sc.Description = "RAZD — Time Tracking & Focus"
    sc.IconLocation = f"{ico_path},0"
    sc.save()

    action = "zaktualizowany" if existed else "utworzony"
    return shortcut_path, f"Skrót {action} na pulpicie:\n{shortcut_path.name}"
