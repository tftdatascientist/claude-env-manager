from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class IntakeView(QWidget):
    qt_start_clicked = Signal(str, str, str)  # prompt, project_name, location

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(QLabel("<b>Nowy projekt Claude Code</b>"))

        form = QFormLayout()
        form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("np. my-app")
        form.addRow("Nazwa projektu:", self._name_edit)

        loc_row = QHBoxLayout()
        self._loc_edit = QLineEdit()
        self._loc_edit.setPlaceholderText("C:\\Users\\Sławek\\projekty")
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_location)
        loc_row.addWidget(self._loc_edit)
        loc_row.addWidget(browse_btn)
        form.addRow("Lokalizacja:", loc_row)

        root.addLayout(form)

        root.addWidget(QLabel("Prompt startowy:"))
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlaceholderText("Opisz cel projektu...")
        self._prompt_edit.setMinimumHeight(120)
        root.addWidget(self._prompt_edit)

        self._start_btn = QPushButton("Start CC")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)
        root.addWidget(self._start_btn)

    def _browse_location(self) -> None:
        current = self._loc_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Wybierz folder", current)
        if chosen:
            self._loc_edit.setText(chosen)

    def _on_start(self) -> None:
        name = self._name_edit.text().strip()
        location = self._loc_edit.text().strip()
        prompt = self._prompt_edit.toPlainText().strip()

        errors: list[str] = []
        if not name:
            errors.append("Podaj nazwę projektu.")
        elif any(c in name for c in r'\/:*?"<>|'):
            errors.append("Nazwa projektu zawiera niedozwolone znaki.")
        if not location:
            errors.append("Wybierz lokalizację projektu.")
        elif not Path(location).is_dir():
            errors.append(f"Folder nie istnieje: {location}")
        if not prompt:
            errors.append("Wpisz prompt startowy.")

        if errors:
            QMessageBox.warning(self, "Błąd walidacji", "\n".join(errors))
            return

        logger.debug("qt_start_clicked name=%s location=%s", name, location)
        self.qt_start_clicked.emit(prompt, name, location)
