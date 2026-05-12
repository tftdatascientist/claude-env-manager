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
    Rysuje ikonę RAZD (białe R na niebieskim tle).
    Próbuje zapisać wielowarstwowy ICO przez Pillow (16/32/48/256px).
    Fallback: ICO przez Qt (tylko 256px) lub PNG.
    """
    import io
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    output = Path(__file__).parent.parent / "RAZD.ico"

    def _render(size: int) -> QPixmap:
        px = QPixmap(size, size)
        px.fill(QColor("#1565C0"))
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", max(8, int(size * 0.60)), QFont.Weight.Bold))
        painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "R")
        painter.end()
        return px

    try:
        from PIL import Image as _Image

        pil_images: list[_Image.Image] = []
        for sz in (16, 32, 48, 256):
            buf = io.BytesIO()
            _render(sz).save(buf, "PNG")
            buf.seek(0)
            pil_images.append(_Image.open(buf).copy())

        pil_images[0].save(
            str(output),
            format="ICO",
            sizes=[(img.width, img.height) for img in pil_images],
            append_images=pil_images[1:],
        )
        return output
    except ImportError:
        pass

    # Fallback Qt — zapisuje 256px ICO
    px256 = _render(256)
    if not px256.save(str(output), "ICO"):
        output = output.with_suffix(".png")
        px256.save(str(output), "PNG")
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
