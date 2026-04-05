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

    def clear(self) -> None:
        self._editor.clear()
        self._header.setText("Select a resource from the tree")
        self._header.setStyleSheet("padding: 4px; color: #666;")
        self._current_resource = None
