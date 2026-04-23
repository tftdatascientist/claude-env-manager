"""Active Projects panel — browse files of pinned projects."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QTreeView, QPlainTextEdit, QLabel, QMenu, QApplication, QFileSystemModel,
    QStyledItemDelegate, QStyleOptionViewItem,
)

from src.utils.active_projects import load_active_projects

# Directories that get gray italic styling
SPECIAL_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", ".env",
    "dist", "build", ".next", ".cache", ".tox", ".egg-info",
    "egg-info", ".mypy_cache", ".pytest_cache", ".ruff_cache",
})


class _SpecialDirDelegate(QStyledItemDelegate):
    """Custom delegate that renders special directories in gray italic."""

    def __init__(self, model: QFileSystemModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        if not index.isValid():
            return
        # Only style the name column
        if index.column() != 0:
            return
        file_info = self._model.fileInfo(index)
        if file_info.isDir() and file_info.fileName() in SPECIAL_DIRS:
            option.font.setItalic(True)
            option.palette.setColor(option.palette.ColorRole.Text, QColor("#808080"))


class ActiveProjectsPanel(QWidget):
    """Panel showing file trees of active (pinned) projects."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_root: Path | None = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main horizontal splitter: project list | file tree + preview
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: project list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header = QLabel("Active Projects")
        left_header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;")
        left_layout.addWidget(left_header)

        self._project_list = QListWidget()
        self._project_list.currentItemChanged.connect(self._on_project_selected)
        left_layout.addWidget(self._project_list)

        # Right: file tree + preview
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # File system model
        self._fs_model = QFileSystemModel()
        self._fs_model.setReadOnly(True)

        # File tree
        self._file_tree = QTreeView()
        self._file_tree.setModel(self._fs_model)
        self._file_tree.setAnimated(True)
        self._file_tree.setIndentation(20)
        self._file_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._file_tree.clicked.connect(self._on_file_clicked)
        self._file_tree.doubleClicked.connect(self._on_file_double_clicked)
        self._file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_tree.customContextMenuRequested.connect(self._on_context_menu)
        # Hide Size, Type, Date Modified columns — show only Name
        self._file_tree.setColumnHidden(1, True)
        self._file_tree.setColumnHidden(2, True)
        self._file_tree.setColumnHidden(3, True)
        # Custom delegate for special dirs
        self._delegate = _SpecialDirDelegate(self._fs_model, self._file_tree)
        self._file_tree.setItemDelegate(self._delegate)

        # Preview panel
        self._preview_header = QLabel("Select a file to preview")
        self._preview_header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #666; font-size: 11px;")

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFont(QFont("Consolas", 10))
        self._preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._preview.setPlaceholderText("Click a file to preview its content.")

        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.addWidget(self._preview_header)
        preview_layout.addWidget(self._preview)

        right_splitter.addWidget(self._file_tree)
        right_splitter.addWidget(preview_widget)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([250, 750])

        layout.addWidget(main_splitter)

    def refresh(self) -> None:
        """Reload the list of active projects from disk."""
        self._project_list.clear()
        active = load_active_projects()
        for project_path in active:
            p = Path(project_path)
            item = QListWidgetItem(p.name)
            item.setData(Qt.ItemDataRole.UserRole, project_path)
            item.setToolTip(project_path)
            if p.is_dir():
                item.setForeground(QBrush(QColor("#569cd6")))
            else:
                item.setForeground(QBrush(QColor("#808080")))
            self._project_list.addItem(item)

        if not active:
            self._file_tree.setRootIndex(QModelIndex())
            self._preview.clear()
            self._preview_header.setText("No active projects — check projects in History tab")
            self._preview_header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #666; font-size: 11px;")

    def _on_project_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        project_path = current.data(Qt.ItemDataRole.UserRole)
        if not project_path:
            return
        p = Path(project_path)
        if not p.is_dir():
            self._preview_header.setText(f"Directory not found: {project_path}")
            self._preview_header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #e06c75; font-size: 11px;")
            self._preview.clear()
            return

        self._current_root = p
        root_index = self._fs_model.setRootPath(str(p))
        self._file_tree.setRootIndex(root_index)
        self._preview.clear()
        self._preview_header.setText(f"{project_path}")
        self._preview_header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;")

    def _on_file_clicked(self, index: QModelIndex) -> None:
        """Single click — preview file content."""
        file_path = Path(self._fs_model.filePath(index))
        if not file_path.is_file():
            return

        self._preview_header.setText(str(file_path))
        self._preview_header.setStyleSheet("padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;")

        # Limit preview to reasonable file sizes (1 MB)
        try:
            size = file_path.stat().st_size
            if size > 1_048_576:
                self._preview.setPlainText(f"[File too large to preview: {size:,} bytes]")
                return
            content = file_path.read_text(encoding="utf-8", errors="replace")
            self._preview.setPlainText(content)
        except OSError as e:
            self._preview.setPlainText(f"[Cannot read file: {e}]")

    def _on_file_double_clicked(self, index: QModelIndex) -> None:
        """Double click — open in system default application."""
        file_path = self._fs_model.filePath(index)
        if Path(file_path).is_file():
            os.startfile(file_path)

    def _on_context_menu(self, pos) -> None:
        index = self._file_tree.indexAt(pos)
        if not index.isValid():
            return

        file_path = Path(self._fs_model.filePath(index))
        target_dir = file_path if file_path.is_dir() else file_path.parent

        menu = QMenu(self)

        if target_dir.is_dir():
            menu.addAction("Open in Explorer", lambda: os.startfile(str(target_dir)))
            menu.addAction("Open in VS Code", lambda: subprocess.Popen(["code", str(target_dir)], shell=True))
            menu.addAction(
                "Open terminal here",
                lambda: subprocess.Popen(
                    ["cmd", "/k", f"cd /d {target_dir}"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                ),
            )
            menu.addSeparator()

        menu.addAction("Copy path", lambda: QApplication.clipboard().setText(str(file_path)))

        menu.exec(self._file_tree.viewport().mapToGlobal(pos))
