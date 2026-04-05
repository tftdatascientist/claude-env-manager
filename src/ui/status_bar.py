"""Status bar showing current resource path and scan info."""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel

from src.models.resource import Resource


class StatusBar(QStatusBar):
    """Bottom status bar with resource path and metadata."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._path_label = QLabel("Ready")
        self._info_label = QLabel("")
        self.addWidget(self._path_label, stretch=1)
        self.addPermanentWidget(self._info_label)

    def show_resource_info(self, resource: Resource) -> None:
        self._path_label.setText(str(resource.path))
        parts = []
        parts.append(resource.scope.value)
        parts.append(resource.resource_type.value)
        if resource.read_only:
            parts.append("read-only")
        if resource.last_modified:
            parts.append(resource.last_modified.strftime("%Y-%m-%d %H:%M"))
        self._info_label.setText(" | ".join(parts))

    def show_scan_summary(self, total_resources: int) -> None:
        self._info_label.setText(f"{total_resources} resources found")

    def set_status(self, text: str) -> None:
        self._path_label.setText(text)
