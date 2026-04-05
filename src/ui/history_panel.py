"""History panel for browsing Claude Code prompt history grouped by project/thread."""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTreeWidget,
    QTreeWidgetItem, QLabel, QPlainTextEdit, QSplitter, QMenu,
    QFileDialog, QApplication,
)

from src.models.history import HistoryEntry, load_history
from src.utils.paths import user_history_path
from src.utils.relocations import resolve_path, save_relocation, remove_relocation, load_relocations


class HistoryPanel(QWidget):
    """Panel for browsing prompt history grouped by project and thread."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[HistoryEntry] = []
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(4, 4, 4, 4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search prompts...")
        self._search.textChanged.connect(self._apply_filter)

        self._count_label = QLabel()

        filter_bar.addWidget(QLabel("Search:"))
        filter_bar.addWidget(self._search, stretch=1)
        filter_bar.addWidget(self._count_label)
        layout.addLayout(filter_bar)

        # Splitter: tree + detail
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["", "Messages", "Time range"])
        self._tree.setColumnWidth(0, 600)
        self._tree.setColumnWidth(1, 70)
        self._tree.setColumnWidth(2, 200)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setFont(QFont("Consolas", 10))
        self._detail.setMaximumHeight(180)
        self._detail.setPlaceholderText("Select a message to view full prompt text")

        splitter.addWidget(self._tree)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def _load(self) -> None:
        """Load history from disk."""
        self._entries = load_history(user_history_path())
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Build grouped tree: Project > Thread (session) > Messages."""
        search_text = self._search.text().lower()

        filtered = self._entries
        if search_text:
            filtered = [e for e in filtered if search_text in e.display.lower()]

        # Group by original project path -> session -> [entries]
        projects: dict[str, dict[str, list[HistoryEntry]]] = defaultdict(lambda: defaultdict(list))
        for entry in filtered:
            projects[entry.project][entry.session_id].append(entry)

        # Sort projects by most recent activity
        sorted_projects = sorted(
            projects.items(),
            key=lambda kv: max(e.timestamp for ses in kv[1].values() for e in ses),
            reverse=True,
        )

        self._tree.clear()
        total_messages = 0
        total_threads = 0

        for original_path, sessions in sorted_projects:
            sorted_sessions = sorted(
                sessions.items(),
                key=lambda kv: max(e.timestamp for e in kv[1]),
                reverse=True,
            )

            thread_count = len(sorted_sessions)
            msg_count = sum(len(msgs) for msgs in sorted_sessions)
            total_threads += thread_count
            total_messages += msg_count

            # Resolve through relocations
            resolved_path, was_relocated = resolve_path(original_path)
            project_name = Path(resolved_path).name if resolved_path else "(unknown)"
            path_exists = Path(resolved_path).is_dir() if resolved_path else False

            # Build label
            if was_relocated:
                label = f"{project_name}  —  {resolved_path}  (was: {original_path})"
            else:
                label = f"{project_name}  —  {resolved_path}" if resolved_path else project_name

            project_item = QTreeWidgetItem([
                label,
                f"{msg_count}",
                f"{thread_count} threads",
            ])
            project_item.setFont(0, self._bold_font())
            # Store both original and resolved path
            project_item.setData(0, Qt.ItemDataRole.UserRole, ("project", original_path, resolved_path, was_relocated))

            if path_exists:
                if was_relocated:
                    project_item.setForeground(0, QColor("#4ec9b0"))  # teal = relocated
                    project_item.setToolTip(0, f"Relocated: {original_path} -> {resolved_path}")
                else:
                    project_item.setForeground(0, QColor("#569cd6"))  # blue = ok
                    project_item.setToolTip(0, resolved_path)
            else:
                project_item.setForeground(0, QColor("#808080"))  # gray = missing
                project_item.setToolTip(0, f"{original_path}\n(directory not found — right-click to relocate)")

            for session_id, messages in sorted_sessions:
                messages_chrono = sorted(messages, key=lambda e: e.timestamp)
                first = messages_chrono[0]
                last = messages_chrono[-1]

                first_prompt = first.short_display
                time_range = first.time_str
                if len(messages_chrono) > 1:
                    time_range = f"{first.time_str} - {last.time_str}"

                thread_item = QTreeWidgetItem([
                    f"{first_prompt}",
                    f"{len(messages_chrono)}",
                    time_range,
                ])
                thread_item.setData(0, Qt.ItemDataRole.UserRole, ("thread", session_id, messages_chrono))
                thread_item.setForeground(0, QColor("#dcdcaa"))
                thread_item.setToolTip(0, f"Session: {session_id}")

                for entry in messages_chrono:
                    msg_item = QTreeWidgetItem([
                        f"  {entry.time_str}  {entry.short_display}",
                        "",
                        "",
                    ])
                    msg_item.setData(0, Qt.ItemDataRole.UserRole, ("message", entry))
                    msg_item.setForeground(0, QColor("#cccccc"))

                    thread_item.addChild(msg_item)

                project_item.addChild(thread_item)

            self._tree.addTopLevelItem(project_item)

        self._count_label.setText(
            f"{total_messages} messages / {total_threads} threads / {len(sorted_projects)} projects"
        )

    def _on_item_selected(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            self._detail.clear()
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            self._detail.clear()
            return

        if data[0] == "message":
            entry: HistoryEntry = data[1]
            lines = [
                entry.display,
                "",
                f"Time:    {entry.datetime.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Project: {entry.project}",
                f"Session: {entry.session_id}",
            ]
            if entry.pasted_contents:
                lines.append(f"\nPasted contents: {len(entry.pasted_contents)} item(s)")
                for name, content in entry.pasted_contents.items():
                    lines.append(f"\n--- {name} ---")
                    lines.append(str(content))
            self._detail.setPlainText("\n".join(lines))

        elif data[0] == "thread":
            session_id = data[1]
            messages: list[HistoryEntry] = data[2]
            lines = [f"Thread: {session_id}", f"Project: {messages[0].project}", ""]
            lines.append(f"Messages ({len(messages)}):")
            lines.append("-" * 60)
            for entry in messages:
                lines.append(f"[{entry.time_str}] {entry.display}")
                lines.append("")
            self._detail.setPlainText("\n".join(lines))

        elif data[0] == "project":
            original_path = data[1]
            resolved_path = data[2]
            was_relocated = data[3]
            path_obj = Path(resolved_path) if resolved_path else None
            exists = path_obj.is_dir() if path_obj else False
            lines = [
                f"Project: {path_obj.name if path_obj else '(unknown)'}",
                f"Original path: {original_path}",
            ]
            if was_relocated:
                lines.append(f"Relocated to: {resolved_path}")
            lines.append(f"Status: {'Found' if exists else 'Not found (right-click to relocate)'}")
            self._detail.setPlainText("\n".join(lines))

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return

        project_data = self._get_project_data(item)
        if not project_data:
            return

        original_path = project_data[1]
        resolved_path = project_data[2]
        was_relocated = project_data[3]
        path_obj = Path(resolved_path) if resolved_path else None
        path_exists = path_obj.is_dir() if path_obj else False

        menu = QMenu(self)

        if path_exists:
            menu.addAction("Open in Explorer", lambda: os.startfile(str(path_obj)))
            menu.addAction("Open in VS Code", lambda: subprocess.Popen(["code", str(path_obj)]))
            menu.addAction(
                "Open terminal here",
                lambda: subprocess.Popen(
                    ["cmd", "/k", f"cd /d {path_obj}"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                ),
            )
            menu.addSeparator()

        if not path_exists:
            menu.addAction("Relocate project...", lambda: self._relocate_project(original_path))

        if was_relocated:
            menu.addAction("Remove relocation", lambda: self._remove_relocation(original_path))

        menu.addAction("Copy path", lambda: QApplication.clipboard().setText(resolved_path or original_path))
        if was_relocated:
            menu.addAction("Copy original path", lambda: QApplication.clipboard().setText(original_path))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _get_project_data(self, item: QTreeWidgetItem) -> tuple | None:
        """Walk up to find the project data tuple from any tree item."""
        current = item
        while current is not None:
            data = current.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "project":
                return data
            current = current.parent()
        return None

    def _relocate_project(self, original_path: str) -> None:
        """Open folder picker to set new location for a missing project."""
        project_name = Path(original_path).name if original_path else "project"
        new_path = QFileDialog.getExistingDirectory(
            self,
            f"Locate project: {project_name}",
            str(Path.home()),
        )
        if new_path:
            save_relocation(original_path, new_path)
            self._apply_filter()  # rebuild tree with new relocation

    def _remove_relocation(self, original_path: str) -> None:
        """Remove a relocation mapping and refresh."""
        remove_relocation(original_path)
        self._apply_filter()

    @staticmethod
    def _open_in_explorer(path: Path) -> None:
        os.startfile(str(path))

    @staticmethod
    def _open_in_vscode(path: Path) -> None:
        subprocess.Popen(["code", str(path)])

    @staticmethod
    def _open_terminal(path: Path) -> None:
        subprocess.Popen(["cmd", "/k", f"cd /d {path}"], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _bold_font(self) -> QFont:
        font = QFont()
        font.setBold(True)
        return font

    def refresh(self) -> None:
        self._load()
