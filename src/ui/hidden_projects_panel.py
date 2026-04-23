"""Hidden Projects panel — view and unhide projects hidden from History."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel, QMenu,
    QApplication,
)

from src.utils.hidden_projects import load_hidden_projects, remove_hidden_project
from src.utils.aliases import load_aliases
from src.utils.relocations import resolve_path


class HiddenProjectsPanel(QWidget):
    """Panel listing hidden projects with option to unhide them."""

    project_unhidden = Signal()  # emitted when a project is unhidden

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Hidden projects — right-click to unhide")
        header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;")
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Project", "Path", "Status"])
        self._tree.setColumnWidth(0, 300)
        self._tree.setColumnWidth(1, 500)
        self._tree.setColumnWidth(2, 100)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tree)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("padding: 4px; color: #666; font-size: 11px;")
        layout.addWidget(self._count_label)

    def refresh(self) -> None:
        """Reload the list of hidden projects."""
        self._tree.clear()
        hidden = load_hidden_projects()
        aliases = load_aliases()

        for original_path in hidden:
            resolved, was_relocated = resolve_path(original_path)
            path_to_check = resolved or original_path
            p = Path(path_to_check)
            exists = p.is_dir()

            alias = aliases.get(path_to_check) or aliases.get(original_path)
            display_name = alias if alias else p.name

            status = "Found" if exists else "Missing"
            if was_relocated:
                status = "Relocated"

            item = QTreeWidgetItem([display_name, path_to_check, status])
            item.setData(0, Qt.ItemDataRole.UserRole, original_path)

            font = QFont()
            font.setBold(True)
            item.setFont(0, font)

            if exists:
                item.setForeground(0, QBrush(QColor("#569cd6")))
            else:
                item.setForeground(0, QBrush(QColor("#808080")))

            item.setForeground(1, QBrush(QColor("#808080")))

            self._tree.addTopLevelItem(item)

        self._count_label.setText(f"{len(hidden)} hidden project(s)")

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return

        original_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not original_path:
            return

        menu = QMenu(self)
        menu.addAction("Unhide", lambda: self._unhide_project(original_path))
        menu.addAction("Copy path", lambda: QApplication.clipboard().setText(item.text(1)))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _unhide_project(self, original_path: str) -> None:
        """Remove from hidden list and refresh."""
        remove_hidden_project(original_path)
        self.refresh()
        self.project_unhidden.emit()
