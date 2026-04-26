"""Editor panel for displaying resource content (read-only in Phase 1)."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget, QLabel

from src.models.resource import Resource, ResourceType
from src.utils.security import mask_dict, mask_value
from src.utils import paths


class EditorPanel(QWidget):
    """Right panel showing file content with syntax highlighting placeholder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._header = QLabel("Select a resource from the tree")
        self._header.setStyleSheet("padding: 4px; color: #666;")

        self._editor = QPlainTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.setPlaceholderText("Select a resource from the tree to view its content.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._editor)

        self._current_resource: Resource | None = None

    def show_resource(self, resource: Resource) -> None:
        """Display the content of a resource."""
        self._current_resource = resource

        # Update header
        scope_label = resource.scope.value.upper()
        ro_label = " [READ-ONLY]" if resource.read_only else ""
        self._header.setText(f"{scope_label}: {resource.path}{ro_label}")
        self._header.setStyleSheet(
            "padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;"
        )

        # Handle env vars (content stored inline, not on disk)
        if resource.resource_type == ResourceType.ENV_VAR:
            value = resource.content or ""
            if resource.masked:
                value = mask_value(value)
            self._editor.setPlainText(f"{resource.display_name}={value}")
            return

        # Handle project info (inline content)
        if resource.resource_type == ResourceType.PROJECT_INFO:
            self._editor.setPlainText(resource.content or "")
            return

        # Handle SSH private keys - don't show content
        if resource.masked and resource.display_name.startswith("SSH:"):
            self._editor.setPlainText("[Private key - content hidden for security]")
            return

        # Load content from disk
        content = resource.load_content()
        if content is None:
            self._editor.setPlainText("[File not found or unreadable]")
            return

        # Mask credentials
        if resource.masked and resource.file_format == "json":
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    data = mask_dict(data)
                content = json.dumps(data, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

        self._editor.setPlainText(content)

    def show_project_detail(self, proj: dict) -> None:
        """Display detailed info about a project from the All Projects list."""
        from datetime import datetime

        name = proj["display_name"]
        num = proj["number"]
        self._header.setText(f"PROJECT #{num}: {name}")
        self._header.setStyleSheet(
            "padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;"
        )

        birth_str = datetime.fromtimestamp(proj["birth_ts"]).strftime("%Y-%m-%d %H:%M:%S")
        hash_dir = proj["hash_dir"]

        lines = [
            f"Project #{num}: {name}",
            f"{'=' * 60}",
            "",
            f"Resolved path:  {proj['resolved_path'] or '(unresolved)'}",
            f"Status:         {'EXISTS' if proj['exists'] else 'NOT FOUND (orphaned)'}",
            f"Hash dir:       {hash_dir}",
            f"Created:        {birth_str}",
            "",
            f"Sessions:       {proj['session_count']}",
            f"Memory files:   {proj['memory_count']}",
        ]

        if proj["agent_memory_count"]:
            lines.append(f"Agent memory:   {proj['agent_memory_count']}")

        if proj["total_log_size"]:
            size_mb = proj["total_log_size"] / (1024 * 1024)
            lines.append(f"Log size:       {size_mb:.1f} MB")

        # List memory files
        memory_files = proj.get("memory_files", [])
        if memory_files:
            lines.append("")
            lines.append("Memory files:")
            lines.append("-" * 40)
            for mf in memory_files:
                lines.append(f"  {mf.name}")
                try:
                    content = mf.read_text(encoding="utf-8", errors="replace")
                    # Show first 3 lines of each memory file
                    preview = content.strip().split("\n")[:3]
                    for pl in preview:
                        lines.append(f"    {pl}")
                    if len(content.strip().split("\n")) > 3:
                        lines.append(f"    ...")
                    lines.append("")
                except OSError:
                    lines.append("    [unreadable]")
                    lines.append("")

        # List session files
        session_files = proj.get("session_files", [])
        if session_files:
            lines.append("")
            lines.append("Session logs:")
            lines.append("-" * 40)
            # Sort by modification time, newest first
            sorted_sessions = sorted(session_files, key=lambda f: f.stat().st_mtime, reverse=True)
            for sf in sorted_sessions:
                try:
                    stat = sf.stat()
                    size_kb = stat.st_size / 1024
                    mod_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    lines.append(f"  {sf.stem}  ({size_kb:.0f} KB, {mod_str})")
                except OSError:
                    lines.append(f"  {sf.stem}  [stat error]")

        self._editor.setPlainText("\n".join(lines))
        self._current_resource = None

    def show_welcome(self, managed: int, user: int, projects: int, external: int) -> None:
        """Display a welcome/summary screen with resource counts."""
        total = managed + user + projects + external
        self._header.setText("Claude Manager")
        self._header.setStyleSheet(
            "padding: 4px; background-color: #2d2d2d; color: #ccc; font-size: 11px;"
        )

        lines = [
            "Claude Manager",
            "=" * 50,
            "",
            f"Scanned resources: {total}",
            "",
            f"  Managed (read-only): {managed}",
            f"  User-level:          {user}",
            f"  Projects:            {projects}",
            f"  External:            {external}",
            "",
            "-" * 50,
            "Select a resource from the tree on the left",
            "to view its content here.",
            "",
            "Tree view:",
            "  • Click any file to open it",
            "  • Right-click for context menu (Explorer, VS Code, ...)",
            "  • Use the combo above the tree to switch to 'All Projects'",
            "",
            "Keyboard shortcuts:",
            "  Ctrl+1 .. Ctrl+6  — switch tabs",
            "  F5                — refresh all",
        ]
        self._editor.setPlainText("\n".join(lines))
        self._current_resource = None

    def clear(self) -> None:
        self._editor.clear()
        self._header.setText("Select a resource from the tree")
        self._header.setStyleSheet("padding: 4px; color: #666;")
        self._current_resource = None
