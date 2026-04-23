"""Tree panel showing all discovered Claude Code resources, with switchable project list."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QStandardItem, QStandardItemModel, QFont, QColor, QBrush
from PySide6.QtWidgets import (
    QTreeView, QVBoxLayout, QWidget, QMenu, QApplication, QColorDialog,
    QInputDialog, QListWidget, QListWidgetItem, QStackedWidget, QComboBox,
)

from src.models.resource import Resource, ResourceScope, ResourceType
from src.scanner.indexer import TreeNode
from src.utils.colors import load_colors, save_color, reset_colors, DEFAULT_COLORS
from src.utils.aliases import load_aliases, save_alias, remove_alias
from src.utils.paths import projects_dir
from src.scanner.discovery import _resolve_project_path, _make_display_name


# Custom roles for tree items
RESOURCE_ROLE = Qt.ItemDataRole.UserRole + 1
CATEGORY_LABEL_ROLE = Qt.ItemDataRole.UserRole + 2
# Roles for project list items
PROJECT_DATA_ROLE = Qt.ItemDataRole.UserRole + 3


class TreePanel(QWidget):
    """Left panel with a tree view of all resources."""

    resource_selected = Signal(object)  # emits Resource or None
    refresh_requested = Signal()  # emits when tree needs rebuild (e.g. after rename)
    project_detail_requested = Signal(dict)  # emits project info dict for detail display

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors = load_colors()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # View switcher
        self._view_combo = QComboBox()
        self._view_combo.addItems(["Resources", "All Projects"])
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        layout.addWidget(self._view_combo)

        # Stacked widget: 0=resources tree, 1=project list
        self._stack = QStackedWidget()

        # --- Resources tree (existing) ---
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

        self._stack.addWidget(self._tree)

        # --- Project list (new) ---
        self._project_list = QListWidget()
        self._project_list.setSpacing(0)
        self._project_list.setUniformItemSizes(True)
        self._project_list.currentItemChanged.connect(self._on_project_item_selected)
        self._project_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._project_list.customContextMenuRequested.connect(self._on_project_list_context_menu)
        self._stack.addWidget(self._project_list)

        layout.addWidget(self._stack)

    # ── Resources tree (existing logic) ────────────────────────────

    def populate(self, root: TreeNode) -> None:
        """Populate the tree from a TreeNode hierarchy."""
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["Resources"])

        root_item = self._model.invisibleRootItem()
        for child in root.children:
            self._add_node(root_item, child)

        self._tree.expandAll()

        # Also refresh project list
        self._populate_project_list()

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
            # Category node - bold font + color
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setData(node.label, CATEGORY_LABEL_ROLE)
            color_hex = self._colors.get(node.label)
            if color_hex:
                item.setForeground(QBrush(QColor(color_hex)))

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

        # Check if this is a category node
        category_label = item.data(CATEGORY_LABEL_ROLE)
        if category_label is not None:
            self._show_category_menu(item, category_label, pos)
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
            menu.addAction("Open in VS Code", lambda: subprocess.Popen(["code", str(target_dir)], shell=True))
            menu.addAction(
                "Open terminal here",
                lambda: subprocess.Popen(
                    ["cmd", "/k", f"cd /d {target_dir}"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                ),
            )
            menu.addSeparator()

        menu.addAction("Copy path", lambda: QApplication.clipboard().setText(str(resource.path)))

        # Rename option for projects
        if resource.resource_type == ResourceType.PROJECT_INFO:
            menu.addSeparator()
            aliases = load_aliases()
            project_key = str(resource.path)
            menu.addAction("Rename...", lambda: self._rename_project(project_key, resource.display_name))
            if project_key in aliases:
                menu.addAction("Remove alias", lambda: self._remove_project_alias(project_key))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _show_category_menu(self, item: QStandardItem, label: str, pos) -> None:
        """Show context menu for category nodes with color options."""
        menu = QMenu(self)

        current_color = self._colors.get(label)

        menu.addAction(
            "Change color...",
            lambda: self._change_category_color(item, label, current_color),
        )

        if label in self._colors and label in DEFAULT_COLORS and self._colors[label] != DEFAULT_COLORS[label]:
            menu.addAction(
                "Reset to default color",
                lambda: self._reset_category_color(item, label),
            )

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _change_category_color(self, item: QStandardItem, label: str, current_hex: str | None) -> None:
        """Open color dialog and apply selected color to a category."""
        initial = QColor(current_hex) if current_hex else QColor("#cccccc")
        color = QColorDialog.getColor(initial, self, f"Color for \"{label}\"")
        if color.isValid():
            hex_color = color.name()
            self._colors[label] = hex_color
            save_color(label, hex_color)
            item.setForeground(QBrush(color))

    def _reset_category_color(self, item: QStandardItem, label: str) -> None:
        """Reset a category color to its default."""
        default = DEFAULT_COLORS.get(label, "#cccccc")
        self._colors[label] = default
        save_color(label, default)
        item.setForeground(QBrush(QColor(default)))

    def _rename_project(self, project_path: str, current_name: str) -> None:
        """Show input dialog to rename a project (cosmetic alias only)."""
        new_name, ok = QInputDialog.getText(
            self, "Rename project", "Display name:", text=current_name,
        )
        if ok and new_name.strip() and new_name.strip() != current_name:
            save_alias(project_path, new_name.strip())
            self.refresh_requested.emit()

    def _remove_project_alias(self, project_path: str) -> None:
        """Remove alias, reverting to original folder name."""
        remove_alias(project_path)
        self.refresh_requested.emit()

    # ── View switcher ──────────────────────────────────────────────

    def _on_view_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ── Project list (new) ─────────────────────────────────────────

    def _populate_project_list(self) -> None:
        """Scan ~/.claude/projects/ and build a numbered list sorted by creation date."""
        self._project_list.clear()

        proj_root = projects_dir()
        if not proj_root.is_dir():
            return

        aliases = load_aliases()

        # Collect project info with birth time
        project_entries: list[dict] = []
        for hash_dir in proj_root.iterdir():
            if not hash_dir.is_dir():
                continue

            # Get creation time (birth time)
            try:
                stat = hash_dir.stat()
                # On Windows, st_ctime is creation time
                birth_ts = stat.st_ctime
            except OSError:
                birth_ts = 0.0

            # Resolve real path
            resolved = _resolve_project_path(hash_dir.name)
            resolved_str = str(resolved) if resolved else None
            exists = resolved.is_dir() if resolved else False

            # Display name: alias > last folder name
            folder_name = resolved.name if resolved else _make_display_name(hash_dir.name)
            alias = None
            if resolved_str:
                alias = aliases.get(resolved_str)
            display_name = alias if alias else folder_name

            # Count sessions and memory files
            session_files = list(hash_dir.glob("*.jsonl"))
            session_count = len(session_files)

            memory_dir = hash_dir / "memory"
            memory_files = list(memory_dir.glob("*.md")) if memory_dir.is_dir() else []
            memory_count = len(memory_files)

            # Agent memory
            agent_memory_count = 0
            agents_dir = hash_dir / "agents"
            if agents_dir.is_dir():
                for agent_dir in agents_dir.iterdir():
                    if agent_dir.is_dir():
                        amem = agent_dir / "memory"
                        if amem.is_dir():
                            agent_memory_count += len(list(amem.glob("*.md")))

            # Total size of session logs
            total_log_size = sum(f.stat().st_size for f in session_files if f.is_file())

            project_entries.append({
                "hash_dir": hash_dir,
                "hash_name": hash_dir.name,
                "resolved_path": resolved_str,
                "exists": exists,
                "display_name": display_name,
                "folder_name": folder_name,
                "birth_ts": birth_ts,
                "session_count": session_count,
                "memory_count": memory_count,
                "agent_memory_count": agent_memory_count,
                "memory_files": memory_files,
                "session_files": session_files,
                "total_log_size": total_log_size,
            })

        # Sort by birth time ascending (oldest first) -> number 1 = oldest
        project_entries.sort(key=lambda p: p["birth_ts"])

        # Add items in reverse order so newest is at top, but keep numbering
        for idx, proj in enumerate(project_entries, start=1):
            proj["number"] = idx

        for proj in reversed(project_entries):
            num = proj["number"]
            name = proj["display_name"]
            sessions = proj["session_count"]
            mem = proj["memory_count"] + proj["agent_memory_count"]

            label = f"#{num}  {name}"
            sub_info = []
            if sessions:
                sub_info.append(f"{sessions} ses")
            if mem:
                sub_info.append(f"{mem} mem")
            if sub_info:
                label += f"  ({', '.join(sub_info)})"

            item = QListWidgetItem(label)
            item.setData(PROJECT_DATA_ROLE, proj)

            # Tooltip with full path and dates
            birth_str = datetime.fromtimestamp(proj["birth_ts"]).strftime("%Y-%m-%d %H:%M")
            tip_lines = [
                f"#{num} {name}",
                f"Path: {proj['resolved_path'] or '(unresolved)'}",
                f"Hash: {proj['hash_name']}",
                f"Created: {birth_str}",
                f"Sessions: {proj['session_count']}",
                f"Memory files: {proj['memory_count']}",
            ]
            if proj["agent_memory_count"]:
                tip_lines.append(f"Agent memory: {proj['agent_memory_count']}")
            if proj["total_log_size"]:
                size_mb = proj["total_log_size"] / (1024 * 1024)
                tip_lines.append(f"Log size: {size_mb:.1f} MB")
            item.setToolTip("\n".join(tip_lines))

            # Colors
            if proj["exists"]:
                item.setForeground(QBrush(QColor("#569cd6")))
            else:
                item.setForeground(QBrush(QColor("#808080")))

            font = item.font()
            font.setFamily("Consolas")
            font.setPointSize(9)
            item.setFont(font)
            item.setSizeHint(QSize(0, 20))

            self._project_list.addItem(item)

    def _on_project_item_selected(self, current: QListWidgetItem | None, _prev) -> None:
        """When a project is clicked, emit detail info for display in editor."""
        if current is None:
            return
        proj = current.data(PROJECT_DATA_ROLE)
        if proj is None:
            return
        self.project_detail_requested.emit(proj)

    def _on_project_list_context_menu(self, pos) -> None:
        """Context menu for project list items."""
        item = self._project_list.itemAt(pos)
        if item is None:
            return

        proj = item.data(PROJECT_DATA_ROLE)
        if proj is None:
            return

        menu = QMenu(self)

        resolved = proj["resolved_path"]
        exists = proj["exists"]
        hash_dir: Path = proj["hash_dir"]

        if exists and resolved:
            target_dir = Path(resolved)
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

        # Always allow opening the .claude/projects hash dir
        menu.addAction("Open hash dir in Explorer", lambda: os.startfile(str(hash_dir)))

        menu.addSeparator()
        if resolved:
            menu.addAction("Copy project path", lambda: QApplication.clipboard().setText(resolved))
        menu.addAction("Copy hash name", lambda: QApplication.clipboard().setText(proj["hash_name"]))

        menu.exec(self._project_list.viewport().mapToGlobal(pos))
