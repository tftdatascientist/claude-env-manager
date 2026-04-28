"""Status bar showing current resource path and scan info."""

from __future__ import annotations

from PySide6.QtCore import QTimer
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
        self._script_timer = QTimer(self)
        self._script_timer.setSingleShot(True)
        self._script_timer.timeout.connect(self._clear_script_notice)
        self._prev_status: str = "Ready"

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
        self._prev_status = text
        self._path_label.setText(text)

    def show_script_running(self, cmd: str, ts: str) -> None:
        """Pokaż powiadomienie o uruchomieniu skryptu Pythona przez CC."""
        short = cmd.strip()
        if len(short) > 80:
            short = short[:77] + "..."
        self._prev_status = self._path_label.text()
        self._path_label.setText(f"▶ PYTHON  {ts}  |  {short}")
        self._path_label.setStyleSheet("color: #fbbf24; font-weight: bold;")
        self._script_timer.start(6000)

    def _clear_script_notice(self) -> None:
        self._path_label.setStyleSheet("")
        self._path_label.setText(self._prev_status)
