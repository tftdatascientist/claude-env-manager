from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RazdTimeTrackingTab(QWidget):
    """Zakładka Time Tracking — oś czasu, kategorie, statystyki."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        placeholder = QLabel("Time Tracking — wkrótce")
        placeholder.setStyleSheet("color: #888; font-size: 16px;")
        layout.addWidget(placeholder)
