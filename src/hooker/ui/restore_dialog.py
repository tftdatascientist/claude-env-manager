"""RestoreDialog — wybór i przywrócenie backupu .bak dla settings.json."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.hooker.core import logger as audit_log
from src.hooker.core.persister import list_backups, restore_from_backup


class RestoreDialog(QDialog):
    """Dialog restore z listy backupów .bak dla danego pliku settings.json."""

    def __init__(self, target: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target = target
        self._backups: list[Path] = []
        self.setWindowTitle(f"Restore — {target.name}")
        self.resize(720, 420)
        self._setup_ui()
        self._load_backups()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel(f"<b>Plik docelowy:</b> <code>{self._target}</code>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Lista backupów
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.addWidget(QLabel("Dostępne kopie zapasowe:"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self._list)
        splitter.addWidget(left)

        # Podgląd zawartości
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.addWidget(QLabel("Podgląd wybranego backupu:"))
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet("font-family: monospace; font-size: 11px;")
        right_layout.addWidget(self._preview)
        splitter.addWidget(right)

        splitter.setSizes([280, 420])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox()
        self._btn_restore = buttons.addButton(
            "🔄 Przywróć wybrany backup", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._btn_restore.setEnabled(False)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._do_restore)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_backups(self) -> None:
        self._backups = list_backups(self._target)
        self._list.clear()
        if not self._backups:
            item = QListWidgetItem("(brak backupów)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            return

        for bak in self._backups:
            # Wyciągnij timestamp z nazwy (format: stem.YYYYMMDD_HHMMSS_ffffff.bak)
            parts = bak.name.split(".")
            ts_part = parts[-2] if len(parts) >= 3 else bak.name
            ts_display = ts_part.replace("_", " ", 1).replace("_", ".")
            item = QListWidgetItem(ts_display)
            item.setData(Qt.ItemDataRole.UserRole, bak)
            self._list.addItem(item)

    def _on_select(self, current: QListWidgetItem | None, _prev: object) -> None:
        if current is None:
            self._preview.setPlainText("")
            self._btn_restore.setEnabled(False)
            return

        bak: Path | None = current.data(Qt.ItemDataRole.UserRole)
        if bak is None:
            self._preview.setPlainText("")
            self._btn_restore.setEnabled(False)
            return

        try:
            raw = bak.read_text(encoding="utf-8")
            # Ładny podgląd JSON
            try:
                data = json.loads(raw)
                pretty = json.dumps(data, ensure_ascii=False, indent=2)
                self._preview.setPlainText(pretty)
            except json.JSONDecodeError:
                self._preview.setPlainText(raw)
        except OSError as e:
            self._preview.setPlainText(f"Błąd odczytu: {e}")

        self._btn_restore.setEnabled(True)

    def _do_restore(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        bak: Path | None = item.data(Qt.ItemDataRole.UserRole)
        if bak is None:
            return

        reply = QMessageBox.question(
            self,
            "Potwierdzenie restore",
            f"Przywrócić plik:\n{self._target}\n\nz backupu:\n{bak.name}\n\n"
            "UWAGA: obecna zawartość pliku zostanie nadpisana!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_from_backup(bak, self._target)
            audit_log.log_restore(self._target, bak)
            QMessageBox.information(self, "Restore OK", f"Przywrócono z:\n{bak.name}")
            self.accept()
        except Exception as e:
            audit_log.log_error(self._target, str(e))
            QMessageBox.critical(self, "Błąd restore", str(e))
