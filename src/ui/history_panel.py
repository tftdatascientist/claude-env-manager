"""History panel for browsing Claude Code prompt history grouped by project/thread."""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTreeWidget,
    QTreeWidgetItem, QLabel, QPlainTextEdit, QSplitter, QMenu,
    QFileDialog, QApplication, QInputDialog, QComboBox,
)

from src.models.history import HistoryEntry, load_history
from src.utils.paths import user_history_path
from src.utils.relocations import resolve_path, save_relocation, remove_relocation, load_relocations
from src.utils.aliases import load_aliases, save_alias, remove_alias
from src.utils.active_projects import load_active_projects, add_active_project, remove_active_project
from src.utils.website_projects import load_website_projects, add_website_project, remove_website_project
from src.utils.hidden_projects import load_hidden_projects, add_hidden_project
from src.utils.project_groups import (
    load_groups, create_group, ungroup, remove_from_group, find_group_for, get_grouped_paths,
    rename_group,
)

# Color for grouped projects
GROUP_COLOR = "#e5c07b"  # gold


def _shorten_path(path: str) -> str:
    """Shorten display path by trimming known prefixes."""
    normalized = path.replace("/", "\\")
    # \SER\ — hide up to and including SER
    ser_marker = "\\SER\\"
    idx = normalized.find(ser_marker)
    if idx != -1:
        return normalized[idx + len(ser_marker):]
    # \Documents\!Projekty or \Documents\ — hide up to and including Documents
    doc_marker = "\\Documents\\"
    idx = normalized.find(doc_marker)
    if idx != -1:
        return normalized[idx + len(doc_marker):]
    return path


class HistoryPanel(QWidget):
    """Panel for browsing prompt history grouped by project and thread."""

    active_projects_changed = Signal()   # emitted when Active checkbox is toggled
    website_projects_changed = Signal()  # emitted when Web checkbox is toggled
    project_hidden = Signal()            # emitted when a project is hidden

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[HistoryEntry] = []
        self._ignore_item_changed = False
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

        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Recent activity", "Messages", "Location"])
        self._sort_combo.currentIndexChanged.connect(lambda: self._apply_filter())

        self._count_label = QLabel()

        filter_bar.addWidget(QLabel("Search:"))
        filter_bar.addWidget(self._search, stretch=1)
        filter_bar.addWidget(QLabel("Sort:"))
        filter_bar.addWidget(self._sort_combo)
        filter_bar.addWidget(self._count_label)
        layout.addLayout(filter_bar)

        # Splitter: tree + detail
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["", "Active", "Web", "Messages", "Time range"])
        self._tree.setColumnWidth(0, 550)
        self._tree.setColumnWidth(1, 50)
        self._tree.setColumnWidth(2, 50)
        self._tree.setColumnWidth(3, 70)
        self._tree.setColumnWidth(4, 200)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemChanged.connect(self._on_item_changed)

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

    # ── Build project info ──────────────────────────────────────────

    def _resolve_project(self, original_path: str, aliases: dict) -> dict:
        """Resolve a project path and build display info dict."""
        resolved_path, was_relocated = resolve_path(original_path)
        folder_name = Path(resolved_path).name if resolved_path else "(unknown)"
        path_exists = Path(resolved_path).is_dir() if resolved_path else False
        alias = aliases.get(resolved_path) or aliases.get(original_path)
        project_name = alias if alias else folder_name
        short_path = _shorten_path(resolved_path) if resolved_path else ""
        label = f"{project_name}  —  {short_path}" if resolved_path else project_name

        return {
            "original_path": original_path,
            "resolved_path": resolved_path,
            "was_relocated": was_relocated,
            "folder_name": folder_name,
            "path_exists": path_exists,
            "alias": alias,
            "project_name": project_name,
            "label": label,
        }

    def _build_project_item(
        self,
        info: dict,
        sessions: dict[str, list[HistoryEntry]],
        active: set[str],
        websites: set[str],
        is_group: bool = False,
    ) -> QTreeWidgetItem:
        """Build a QTreeWidgetItem for a project with its threads."""
        sorted_sessions = sorted(
            sessions.items(),
            key=lambda kv: max(e.timestamp for e in kv[1]),
            reverse=True,
        )
        thread_count = len(sorted_sessions)
        msg_count = sum(len(msgs) for msgs in sorted_sessions)

        project_item = QTreeWidgetItem([
            info["label"],
            "",
            "",
            f"{msg_count}",
            f"{thread_count} threads",
        ])
        project_item.setFont(0, self._bold_font())

        check_path = info["resolved_path"] or info["original_path"]
        if info["path_exists"]:
            project_item.setFlags(project_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            project_item.setCheckState(1, Qt.CheckState.Checked if check_path in active else Qt.CheckState.Unchecked)
            project_item.setCheckState(2, Qt.CheckState.Checked if check_path in websites else Qt.CheckState.Unchecked)

        project_item.setData(0, Qt.ItemDataRole.UserRole, (
            "project", info["original_path"], info["resolved_path"], info["was_relocated"],
        ))

        # Colors
        if is_group:
            project_item.setForeground(0, QColor(GROUP_COLOR))
            tooltip = f"[GROUP] {info['resolved_path']}"
            if info["alias"]:
                tooltip = f"[GROUP] Alias: {info['project_name']}\nFolder: {info['folder_name']}\nPath: {info['resolved_path']}"
            project_item.setToolTip(0, tooltip)
        elif info["path_exists"]:
            if info["was_relocated"]:
                project_item.setForeground(0, QColor("#4ec9b0"))
                tooltip = f"Current: {info['resolved_path']}\nOriginal: {info['original_path']}"
                if info["alias"]:
                    tooltip = f"Alias: {info['project_name']}\nFolder: {info['folder_name']}\n{tooltip}"
                project_item.setToolTip(0, tooltip)
            else:
                project_item.setForeground(0, QColor("#569cd6"))
                tooltip = info["resolved_path"]
                if info["alias"]:
                    tooltip = f"Alias: {info['project_name']}\nFolder: {info['folder_name']}\nPath: {info['resolved_path']}"
                project_item.setToolTip(0, tooltip)
        else:
            project_item.setForeground(0, QColor("#808080"))
            project_item.setToolTip(0, f"{info['original_path']}\n(directory not found — right-click to relocate)")

        # Add thread children
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
                "",
                "",
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
                    "",
                    "",
                ])
                msg_item.setData(0, Qt.ItemDataRole.UserRole, ("message", entry))
                msg_item.setForeground(0, QColor("#cccccc"))
                thread_item.addChild(msg_item)

            project_item.addChild(thread_item)

        return project_item, msg_count, thread_count

    # ── Main filter / build ─────────────────────────────────────────

    def _apply_filter(self) -> None:
        """Build grouped tree: Groups first, then ungrouped projects."""
        search_text = self._search.text().lower()

        filtered = self._entries
        if search_text:
            filtered = [e for e in filtered if search_text in e.display.lower()]

        # Group by original project path -> session -> [entries]
        projects: dict[str, dict[str, list[HistoryEntry]]] = defaultdict(lambda: defaultdict(list))
        for entry in filtered:
            projects[entry.project][entry.session_id].append(entry)

        self._tree.clear()
        self._ignore_item_changed = True
        total_messages = 0
        total_threads = 0
        aliases = load_aliases()
        active = set(load_active_projects())
        websites = set(load_website_projects())
        hidden = set(load_hidden_projects())
        groups = load_groups()
        grouped_non_main = get_grouped_paths()  # paths that are non-main members

        # ── Phase 1: Groups (sorted by most recent activity, at top) ──
        group_items: list[tuple[int, QTreeWidgetItem]] = []

        for group in groups:
            # Collect all sessions from all group members
            group_sessions: dict[str, list[HistoryEntry]] = defaultdict(list)
            max_ts = 0
            for member_path in group.members:
                if member_path in hidden:
                    continue
                if member_path in projects:
                    for sid, entries in projects[member_path].items():
                        group_sessions[sid].extend(entries)
                    for ses in projects[member_path].values():
                        for e in ses:
                            if e.timestamp > max_ts:
                                max_ts = e.timestamp

            if not group_sessions:
                continue

            # Use main project info for the group label
            main_info = self._resolve_project(group.main, aliases)

            # Use custom group name if set, otherwise fall back to main project name
            display_name = group.name if group.name else main_info['project_name']

            # Build a group wrapper node
            group_item = QTreeWidgetItem([
                f"▸ {display_name}  ({len(group.members)} projects)",
                "",
                "",
                "",
                "",
            ])
            group_item.setFont(0, self._bold_font())
            group_item.setForeground(0, QColor(GROUP_COLOR))
            group_item.setData(0, Qt.ItemDataRole.UserRole, ("group", group.main, [m for m in group.members]))
            members_list = "\n".join(f"  • {Path(m).name}" for m in group.members)
            tooltip_title = display_name if group.name else f"Group ({len(group.members)} projects)"
            group_item.setToolTip(0, f"{tooltip_title}:\n{members_list}")

            group_msg = 0
            group_thr = 0

            # Add each member as a sub-project under the group
            for member_path in group.members:
                if member_path in hidden:
                    continue
                if member_path not in projects:
                    continue
                member_info = self._resolve_project(member_path, aliases)
                is_main = member_path == group.main
                member_item, mc, tc = self._build_project_item(
                    member_info, projects[member_path], active, websites, is_group=False,
                )
                # Color member projects in group gold
                member_item.setForeground(0, QColor(GROUP_COLOR))
                if is_main:
                    # Mark main with a star
                    member_item.setText(0, f"★ {member_item.text(0)}")
                group_item.addChild(member_item)
                group_msg += mc
                group_thr += tc

            group_item.setText(3, f"{group_msg}")
            group_item.setText(4, f"{group_thr} threads")
            total_messages += group_msg
            total_threads += group_thr

            group_items.append((len(group.members), group_item))

        # Sort groups by member count (more members = higher)
        group_items.sort(key=lambda x: x[0], reverse=True)
        for _, gi in group_items:
            self._tree.addTopLevelItem(gi)

        # ── Phase 2: Ungrouped projects ──
        sort_mode = self._sort_combo.currentText()

        # Collect ungrouped project data for sorting
        ungrouped: list[tuple[str, dict[str, list[HistoryEntry]]]] = []
        for original_path, sessions in projects.items():
            if original_path in hidden:
                continue
            if original_path in grouped_non_main:
                continue
            if any(g.main == original_path for g in groups):
                continue
            ungrouped.append((original_path, sessions))

        if sort_mode == "Messages":
            ungrouped.sort(
                key=lambda kv: sum(len(msgs) for msgs in kv[1].values()),
                reverse=True,
            )
        elif sort_mode == "Location":
            ungrouped.sort(
                key=lambda kv: resolve_path(kv[0])[0].lower() if resolve_path(kv[0])[0] else kv[0].lower(),
            )
        else:  # Recent activity (default)
            ungrouped.sort(
                key=lambda kv: max(e.timestamp for ses in kv[1].values() for e in ses),
                reverse=True,
            )

        for original_path, sessions in ungrouped:
            info = self._resolve_project(original_path, aliases)
            project_item, mc, tc = self._build_project_item(info, sessions, active, websites)
            total_messages += mc
            total_threads += tc
            self._tree.addTopLevelItem(project_item)

        self._ignore_item_changed = False

        self._count_label.setText(
            f"{total_messages} messages / {total_threads} threads / {len(ungrouped)} projects"
        )

    # ── Checkbox handling ───────────────────────────────────────────

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle checkbox toggle on project items (col 1 = Active, col 2 = Web)."""
        if self._ignore_item_changed or column not in (1, 2):
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "project":
            return
        resolved_path = data[2]
        original_path = data[1]
        check_path = resolved_path or original_path
        checked = item.checkState(column) == Qt.CheckState.Checked

        if column == 1:
            if checked:
                add_active_project(check_path)
            else:
                remove_active_project(check_path)
            self.active_projects_changed.emit()
        elif column == 2:
            if checked:
                add_website_project(check_path)
            else:
                remove_website_project(check_path)
            self.website_projects_changed.emit()

    # ── Detail panel ────────────────────────────────────────────────

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
            group = find_group_for(original_path)
            if group:
                group_label = group.name if group.name else Path(group.main).name
                lines.append(f"\nGroup: {group_label}")
                lines.append(f"Group members ({len(group.members)}):")
                for m in group.members:
                    marker = " ★" if m == group.main else ""
                    lines.append(f"  • {Path(m).name}{marker}")
            self._detail.setPlainText("\n".join(lines))

        elif data[0] == "group":
            main_path = data[1]
            members = data[2]
            group = find_group_for(main_path)
            group_title = group.name if group and group.name else Path(main_path).name
            lines = [f"Group: {group_title}", f"Members ({len(members)}):"]
            for m in members:
                marker = " ★ (main)" if m == main_path else ""
                lines.append(f"  • {Path(m).name}{marker}")
            self._detail.setPlainText("\n".join(lines))

    # ── Context menu ────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return

        # Check if multiple project-level items are selected (for grouping)
        selected_projects = self._get_selected_project_paths()
        if len(selected_projects) >= 2:
            menu = QMenu(self)
            menu.addAction(
                f"Group selected ({len(selected_projects)} projects)...",
                lambda: self._group_selected(selected_projects),
            )
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return

        # Check if clicked on a group node
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data[0] == "group":
            menu = QMenu(self)
            main_path = data[1]
            menu.addAction("Rename group...", lambda: self._rename_group(main_path))
            menu.addAction("Ungroup", lambda: self._ungroup(main_path))
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return

        # Single project context menu
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
            menu.addAction("Open in VS Code", lambda: subprocess.Popen(["code", str(path_obj)], shell=True))
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

        # Rename alias
        menu.addSeparator()
        alias_key = resolved_path or original_path
        current_name = Path(resolved_path).name if resolved_path else Path(original_path).name
        aliases = load_aliases()
        display_name = aliases.get(alias_key, current_name)
        menu.addAction("Rename...", lambda: self._rename_project(alias_key, display_name))
        if alias_key in aliases:
            menu.addAction("Remove alias", lambda: self._remove_alias(alias_key))

        # Group options for single project
        group = find_group_for(original_path)
        if group:
            menu.addSeparator()
            menu.addAction("Remove from group", lambda: self._remove_from_group(original_path))
            if original_path != group.main:
                menu.addAction("Set as group main", lambda: self._set_as_main(original_path, group))

        menu.addSeparator()
        menu.addAction("Hide", lambda: self._hide_project(original_path))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _get_selected_project_paths(self) -> list[str]:
        """Get original_paths of all selected project-level items."""
        paths = []
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "project":
                paths.append(data[1])  # original_path
        return paths

    # ── Actions ─────────────────────────────────────────────────────

    def _get_project_data(self, item: QTreeWidgetItem) -> tuple | None:
        """Walk up to find the project data tuple from any tree item."""
        current = item
        while current is not None:
            data = current.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "project":
                return data
            current = current.parent()
        return None

    def _group_selected(self, original_paths: list[str]) -> None:
        """Create a group from selected projects, asking which is main."""
        # Build display names for the dialog
        aliases = load_aliases()
        names = []
        for p in original_paths:
            resolved, _ = resolve_path(p)
            alias = aliases.get(resolved) or aliases.get(p)
            name = alias if alias else Path(resolved).name
            names.append(name)

        main_name, ok = QInputDialog.getItem(
            self,
            "Select main project",
            "Which project should be the main (displayed at top)?",
            names,
            0,
            False,
        )
        if not ok:
            return

        main_idx = names.index(main_name)
        main_path = original_paths[main_idx]
        create_group(main_path, original_paths)
        self._apply_filter()

    def _rename_group(self, main_path: str) -> None:
        """Set a custom display name for a group."""
        # Find current name
        group = find_group_for(main_path)
        current_name = group.name if group and group.name else ""

        name, ok = QInputDialog.getText(
            self,
            "Rename group",
            "Group name (leave empty to reset):",
            text=current_name,
        )
        if not ok:
            return
        rename_group(main_path, name.strip())
        self._apply_filter()

    def _ungroup(self, main_path: str) -> None:
        """Dissolve a group."""
        ungroup(main_path)
        self._apply_filter()

    def _remove_from_group(self, project_path: str) -> None:
        """Remove a single project from its group."""
        remove_from_group(project_path)
        self._apply_filter()

    def _set_as_main(self, project_path: str, group) -> None:
        """Change the main project in a group."""
        # Recreate group with new main
        create_group(project_path, group.members)
        self._apply_filter()

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
            self._apply_filter()

    def _remove_relocation(self, original_path: str) -> None:
        """Remove a relocation mapping and refresh."""
        remove_relocation(original_path)
        self._apply_filter()

    def _rename_project(self, project_path: str, current_name: str) -> None:
        """Show input dialog to set a display alias for a project."""
        new_name, ok = QInputDialog.getText(
            self, "Rename project", "Display name:", text=current_name,
        )
        if ok and new_name.strip() and new_name.strip() != current_name:
            save_alias(project_path, new_name.strip())
            self._apply_filter()

    def _remove_alias(self, project_path: str) -> None:
        """Remove alias and revert to folder name."""
        remove_alias(project_path)
        self._apply_filter()

    def _hide_project(self, original_path: str) -> None:
        """Hide a project from the history list."""
        add_hidden_project(original_path)
        self._apply_filter()
        self.project_hidden.emit()

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
