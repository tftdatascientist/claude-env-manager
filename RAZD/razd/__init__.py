from __future__ import annotations

from razd.ui.main_window import RazdMainWindow

__all__ = ["RazdMainWindow", "register_menu"]


def register_menu(menu_bar) -> None:
    """Rejestracja RAZD w QMenuBar CEM."""
    from PySide6.QtGui import QAction

    menu = menu_bar.addMenu("RAZD")

    open_action = QAction("Otwórz RAZD", menu_bar)
    open_action.triggered.connect(_open_window)
    menu.addAction(open_action)


_window: RazdMainWindow | None = None


def _open_window() -> None:
    global _window
    if _window is None:
        _window = RazdMainWindow()
    _window.show()
    _window.raise_()
    _window.activateWindow()
