from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RazdFocusTimerTab(QWidget):
    """Zakładka Focus Timer — whitelist appek, timer 30-120min, alerty."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        placeholder = QLabel("Focus Timer — wkrótce")
        placeholder.setStyleSheet("color: #888; font-size: 16px;")
        layout.addWidget(placeholder)
