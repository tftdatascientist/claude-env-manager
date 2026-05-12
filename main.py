"""Entry point for Claude Manager."""

import ctypes
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from src.ui.main_window import MainWindow

_ASSETS = Path(__file__).parent / "assets"
_ICON_ICO = _ASSETS / "cm.ico"
_ICON_TRAY_ICO = _ASSETS / "cm_tray.ico"


def _make_cm_icon(ico_path: Path) -> QIcon:
    """Białe CM na niebieskim tle — analogicznie do RAZD."""
    if ico_path.exists():
        return QIcon(str(ico_path))
    return _make_cm_icon_fallback()


def _make_cm_icon_fallback() -> QIcon:
    icon = QIcon()
    for size in (16, 32, 48, 64, 256):
        icon.addPixmap(_draw_cm_px(size))
    return icon


def _draw_cm_px(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(QColor("#1565C0"))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("white"))
    p.setFont(QFont("Arial", max(6, int(size * 0.42)), QFont.Weight.Bold))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "CM")
    p.end()
    return px


def _set_taskbar_icon(window) -> None:
    """Wysyła WM_SETICON bezpośrednio do okna — jedyna niezawodna metoda na Windows 11."""
    ico = _ICON_ICO if _ICON_ICO.exists() else None
    if ico is None:
        return
    user32 = ctypes.windll.user32
    hicon_big = user32.LoadImageW(None, str(ico), 1, 32, 32, 0x10)   # LR_LOADFROMFILE
    hicon_small = user32.LoadImageW(None, str(ico), 1, 16, 16, 0x10)
    if not hicon_big:
        return
    hwnd = int(window.winId())
    WM_SETICON = 0x0080
    user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)   # ICON_BIG
    user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)  # ICON_SMALL


def main() -> None:
    # Bez tego Windows grupuje okno pod ikoną python.exe na pasku zadań
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Automatyczni.ClaudeManager.1")

    app = QApplication(sys.argv)
    app.setApplicationName("Claude Manager")
    app.setApplicationVersion("0.1.0")

    icon = _make_cm_icon(_ICON_ICO)
    app.setWindowIcon(icon)

    # Dark theme stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e1e;
        }
        QTreeView {
            background-color: #252526;
            color: #cccccc;
            border: none;
            font-size: 13px;
        }
        QTreeView::item:selected {
            background-color: #094771;
        }
        QTreeView::item:hover {
            background-color: #2a2d2e;
        }
        QHeaderView::section {
            background-color: #333333;
            color: #cccccc;
            padding: 4px;
            border: none;
        }
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            selection-background-color: #264f78;
        }
        QMenuBar {
            background-color: #333333;
            color: #cccccc;
        }
        QMenuBar::item:selected {
            background-color: #094771;
        }
        QMenu {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #454545;
        }
        QMenu::item:selected {
            background-color: #094771;
        }
        QStatusBar {
            background-color: #007acc;
            color: white;
            font-size: 12px;
        }
        QLabel {
            color: #cccccc;
        }
        QSplitter::handle {
            background-color: #3c3c3c;
            width: 5px;
            margin: 0 1px;
        }
        QSplitter::handle:hover {
            background-color: #007acc;
        }
        QSplitter::handle:pressed {
            background-color: #005f9e;
        }
        QMessageBox {
            background-color: #252526;
        }
        QMessageBox QLabel {
            color: #cccccc;
        }
        QTabWidget::pane {
            border: none;
            background-color: #1e1e1e;
        }
        QTabBar::tab {
            background-color: #2d2d2d;
            color: #969696;
            padding: 6px 16px;
            border: none;
            border-bottom: 2px solid transparent;
        }
        QTabBar::tab:selected {
            color: #ffffff;
            background-color: #1e1e1e;
            border-bottom: 2px solid #007acc;
        }
        QTabBar::tab:hover {
            color: #cccccc;
        }
        QTreeWidget {
            background-color: #1e1e1e;
            color: #cccccc;
            border: none;
            font-size: 12px;
            alternate-background-color: #252526;
        }
        QTreeWidget::item:selected {
            background-color: #094771;
        }
        QTreeWidget::item:hover {
            background-color: #2a2d2e;
        }
        QLineEdit {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #454545;
            padding: 4px 8px;
            border-radius: 2px;
        }
        QLineEdit:focus {
            border-color: #007acc;
        }
        QComboBox {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #454545;
            padding: 4px 8px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #252526;
            color: #cccccc;
            selection-background-color: #094771;
        }
    """)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    _set_taskbar_icon(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
