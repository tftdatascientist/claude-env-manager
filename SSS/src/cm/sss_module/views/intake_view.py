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
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class IntakeView(QWidget):
    qt_start_clicked = Signal(str, str, str)    # prompt, project_name, location
    qt_resume_clicked = Signal(str)             # project_dir

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- przełącznik trybu ---
        mode_row = QHBoxLayout()
        self._btn_new = QPushButton("Nowy projekt")
        self._btn_new.setCheckable(True)
        self._btn_new.setChecked(True)
        self._btn_new.clicked.connect(lambda: self._set_mode("new"))
        self._btn_resume = QPushButton("Kontynuuj projekt")
        self._btn_resume.setCheckable(True)
        self._btn_resume.clicked.connect(lambda: self._set_mode("resume"))
        mode_row.addWidget(self._btn_new)
        mode_row.addWidget(self._btn_resume)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # --- stack: strona Nowy / strona Kontynuuj ---
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_new_page())
        self._stack.addWidget(self._build_resume_page())
        root.addWidget(self._stack)

    def _build_new_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(QLabel("<b>Nowy projekt Claude Code</b>"))

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

        lay.addLayout(form)

        lay.addWidget(QLabel("Prompt startowy:"))
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlaceholderText("Opisz cel projektu...")
        self._prompt_edit.setMinimumHeight(100)
        lay.addWidget(self._prompt_edit)

        self._start_btn = QPushButton("Start CC")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._on_start)
        lay.addWidget(self._start_btn)

        return page

    def _build_resume_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(QLabel("<b>Kontynuuj istniejący projekt</b>"))

        form = QFormLayout()
        form.setSpacing(8)

        dir_row = QHBoxLayout()
        self._resume_dir_edit = QLineEdit()
        self._resume_dir_edit.setPlaceholderText("Wybierz katalog projektu CC...")
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_resume_dir)
        dir_row.addWidget(self._resume_dir_edit)
        dir_row.addWidget(browse_btn)
        form.addRow("Katalog projektu:", dir_row)

        lay.addLayout(form)
        lay.addStretch()

        self._resume_btn = QPushButton("Wznów CC")
        self._resume_btn.setFixedHeight(36)
        self._resume_btn.clicked.connect(self._on_resume)
        lay.addWidget(self._resume_btn)

        return page

    def _set_mode(self, mode: str) -> None:
        is_new = mode == "new"
        self._btn_new.setChecked(is_new)
        self._btn_resume.setChecked(not is_new)
        self._stack.setCurrentIndex(0 if is_new else 1)

    def _browse_location(self) -> None:
        current = self._loc_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Wybierz folder nadrzędny", current)
        if chosen:
            self._loc_edit.setText(chosen)

    def _browse_resume_dir(self) -> None:
        current = self._resume_dir_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Wybierz katalog projektu", current)
        if chosen:
            self._resume_dir_edit.setText(chosen)

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

    def _on_resume(self) -> None:
        project_dir = self._resume_dir_edit.text().strip()

        if not project_dir:
            QMessageBox.warning(self, "Błąd walidacji", "Wybierz katalog projektu.")
            return
        if not Path(project_dir).is_dir():
            QMessageBox.warning(self, "Błąd walidacji", f"Folder nie istnieje: {project_dir}")
            return

        logger.debug("qt_resume_clicked project_dir=%s", project_dir)
        self.qt_resume_clicked.emit(project_dir)
