"""Tree panel showing all discovered Claude Code resources."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel, QFont
from PySide6.QtWidgets import QTreeView, QVBoxLayout, QWidget, QMenu, QApplication

from src.models.resource import Resource, ResourceScope, ResourceType
from src.scanner.indexer import TreeNode

# Role for storing Resource reference on tree items
RESOURCE_ROLE = Qt.ItemDataRole.UserRole + 1


class TreePanel(QWidget):
    """Left panel with a tree view of all resources."""

    resource_selected = Signal(object)  # emits Resource or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Resources"])

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(False)
        self._tree.setAnimated(True)
        self._tree.setIndentation(20)
        self._tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._tree.clicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    def populate(self, root: TreeNode) -> None:
        """Populate the tree from a TreeNode hierarchy."""
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["Resources"])

        root_item = self._model.invisibleRootItem()
        for child in root.children:
            self._add_node(root_item, child)

        self._tree.expandAll()

    def _add_node(self, parent_item: QStandardItem, node: TreeNode) -> None:
        item = QStandardItem(node.label)
        item.setEditable(False)

        if node.resource:
            item.setData(node.resource, RESOURCE_ROLE)
            if node.resource.scope == ResourceScope.MANAGED:
                item.setToolTip("Read-only (managed policy)")
            if node.resource.masked:
                item.setToolTip("Sensitive - values masked")
        else:
            # Category node - bold font
            font = item.font()
            font.setBold(True)
            item.setFont(font)

        parent_item.appendRow(item)

        for child in node.children:
            self._add_node(item, child)

    def _on_item_clicked(self, index) -> None:
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        resource = item.data(RESOURCE_ROLE)
        if resource is not None:
            self.resource_selected.emit(resource)

    def _on_context_menu(self, pos) -> None:
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return

        item = self._model.itemFromIndex(index)
        if item is None:
            return

        resource: Resource | None = item.data(RESOURCE_ROLE)
        if resource is None:
            return

        # Determine the directory to act on
        target = resource.path
        if resource.resource_type == ResourceType.PROJECT_INFO:
            target_dir = target  # root_path is already a directory
        elif target.is_dir():
            target_dir = target
        else:
            target_dir = target.parent

        menu = QMenu(self)

        if target_dir.is_dir():
            menu.addAction("Open in Explorer", lambda: os.startfile(str(target_dir)))
            menu.addAction("Open in VS Code", lambda: subprocess.Popen(["code", str(target_dir)]))
            menu.addAction(
                "Open terminal here",
                lambda: subprocess.Popen(
                    ["cmd", "/k", f"cd /d {target_dir}"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                ),
            )
            menu.addSeparator()

        menu.addAction("Copy path", lambda: QApplication.clipboard().setText(str(resource.path)))

        menu.exec(self._tree.viewport().mapToGlobal(pos))
