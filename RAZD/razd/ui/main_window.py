from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from razd.ui.time_tracking_tab import RazdTimeTrackingTab
from razd.ui.focus_timer_tab import RazdFocusTimerTab


class RazdMainWindow(QMainWindow):
    """Główne okno modułu RAZD."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAZD — Time Tracking & Focus")
        self.setMinimumSize(900, 600)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        tabs = QTabWidget()
        tabs.addTab(RazdTimeTrackingTab(), "Time Tracking")
        tabs.addTab(RazdFocusTimerTab(), "Focus Timer")
        self.setCentralWidget(tabs)
