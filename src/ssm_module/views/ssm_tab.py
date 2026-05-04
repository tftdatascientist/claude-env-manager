"""ssm_tab.py — główny widok SSM Monitor w CM (QTabWidget per projekt SSS)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..core.ssm_service import MAX_PROJECTS, SSMService
from .project_tab import ProjectTab


class SsmTab(QWidget):
    """Zakładka 'SSS Monitor' — podłącza się do SSMService, nie zarządza watcherami."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service = SSMService.instance()
        self._project_tabs: dict[str, ProjectTab] = {}
        self._build_ui()
        self._load_from_service()
        self._service.project_updated.connect(self._on_project_updated)
        self._service.project_added.connect(self._on_project_auto_added)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        title = QLabel('SSS Monitor')
        title.setStyleSheet('color:#cba6f7;font-size:15px;font-weight:bold;')
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._capacity_label = QLabel(f'0 / {MAX_PROJECTS}')
        self._capacity_label.setStyleSheet('color:#585b70;font-size:12px;margin-right:8px;')
        toolbar.addWidget(self._capacity_label)

        add_btn = QPushButton('+ Dodaj projekt SSS')
        add_btn.clicked.connect(self._on_add_project)
        toolbar.addWidget(add_btn)

        remove_btn = QPushButton('Usuń')
        remove_btn.clicked.connect(self._on_remove_project)
        toolbar.addWidget(remove_btn)

        layout.addLayout(toolbar)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(False)
        layout.addWidget(self._tabs)

        self._placeholder = QLabel(
            'Brak monitorowanych projektów SSS.\n'
            'Kliknij „+ Dodaj projekt SSS" aby dodać.\n\n'
            f'SSM monitoruje projekty w tle gdy CM jest uruchomiony (max {MAX_PROJECTS}).'
        )
        self._placeholder.setStyleSheet('color:#585b70;font-size:13px;')
        self._placeholder.setWordWrap(True)
        layout.addWidget(self._placeholder)

    def _load_from_service(self) -> None:
        for entry in self._service.projects():
            self._add_tab(entry.project_id, Path(entry.path), entry.name or entry.project_id)
        self._sync_ui()

    def _add_tab(self, pid: str, path: Path, name: str) -> None:
        if pid in self._project_tabs:
            return
        snap = self._service.snapshot(pid)
        tab = ProjectTab(path, name, initial_snapshot=snap)
        self._project_tabs[pid] = tab
        self._tabs.addTab(tab, name)

    def _remove_tab(self, pid: str) -> None:
        tab = self._project_tabs.pop(pid, None)
        if tab is None:
            return
        idx = self._tabs.indexOf(tab)
        if idx >= 0:
            self._tabs.removeTab(idx)
        tab.deleteLater()

    def _on_project_auto_added(self, pid: str) -> None:
        """Obsługuje projekt auto-wykryty przez hook SessionStart."""
        entry = next((e for e in self._service.projects() if e.project_id == pid), None)
        if entry:
            self._add_tab(pid, Path(entry.path), entry.name or pid)
            self._sync_ui()

    def _on_project_updated(self, pid: str) -> None:
        tab = self._project_tabs.get(pid)
        if tab:
            snap = self._service.snapshot(pid)
            if snap is not None:
                tab.apply_snapshot(snap)

    def _on_add_project(self) -> None:
        if not self._service.can_add():
            QMessageBox.warning(
                self, 'Limit projektów',
                f'Można monitorować maksymalnie {MAX_PROJECTS} projekty SSS jednocześnie.'
            )
            return
        path_str = QFileDialog.getExistingDirectory(
            self, 'Wybierz katalog projektu SSS', str(Path.home())
        )
        if not path_str:
            return
        ok, msg = self._service.add_project(Path(path_str))
        if not ok:
            QMessageBox.warning(self, 'Błąd dodawania projektu', msg)
            return
        path = Path(path_str)
        entry = next(
            (e for e in self._service.projects()
             if str(Path(e.path).resolve()) == str(path.resolve())),
            None,
        )
        if entry:
            self._add_tab(entry.project_id, Path(entry.path), entry.name or entry.project_id)
        self._sync_ui()

    def _on_remove_project(self) -> None:
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        pid = list(self._project_tabs.keys())[idx]
        self._service.remove_project(pid)
        self._remove_tab(pid)
        self._sync_ui()

    def _sync_ui(self) -> None:
        count = self._tabs.count()
        self._capacity_label.setText(f'{count} / {MAX_PROJECTS}')
        self._placeholder.setVisible(count == 0)
        self._tabs.setVisible(count > 0)
