"""project_tab.py — pojedynczy tab monitorowanego projektu SSS."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ..core.hook_installer import install_hook, is_hook_installed
from ..core.project_state import ProjectSnapshot, load_snapshot


class ProjectTab(QWidget):
    def __init__(
        self,
        project_path: Path,
        project_name: str = '',
        initial_snapshot: Optional[ProjectSnapshot] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._path = project_path
        self._name = project_name or project_path.name
        self._build_ui()
        if initial_snapshot is not None:
            self.apply_snapshot(initial_snapshot)
        else:
            self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Badge: hook nie zainstalowany ---
        self._badge_widget = QFrame()
        self._badge_widget.setStyleSheet(
            'background:#7c5a00;border-radius:4px;padding:4px;'
        )
        badge_layout = QHBoxLayout(self._badge_widget)
        badge_layout.setContentsMargins(8, 4, 8, 4)
        badge_label = QLabel('⚠ Hook SSM nie zainstalowany w tym projekcie')
        badge_label.setStyleSheet('color:#ffd54f;font-weight:bold;')
        badge_layout.addWidget(badge_label)
        install_btn = QPushButton('Zainstaluj hook SSM')
        install_btn.setFixedWidth(160)
        install_btn.clicked.connect(self._on_install_hook)
        badge_layout.addWidget(install_btn)
        self._badge_widget.hide()
        layout.addWidget(self._badge_widget)

        # --- Statystyki ---
        stats_frame = QFrame()
        stats_frame.setStyleSheet('background:#1e1e2e;border-radius:6px;')
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 8, 12, 8)

        self._lbl_round = QLabel('Runda: —')
        self._lbl_session = QLabel('Sesja: —')
        self._lbl_next = QLabel('Next: —')
        self._lbl_done = QLabel('Done: —')
        self._lbl_repo = QLabel('')
        self._lbl_last_event = QLabel('')

        for lbl in (self._lbl_round, self._lbl_session, self._lbl_next, self._lbl_done):
            lbl.setStyleSheet('color:#cdd6f4;font-size:13px;')
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()
        self._lbl_last_event.setStyleSheet('color:#585b70;font-size:11px;')
        stats_layout.addWidget(self._lbl_last_event)
        self._lbl_repo.setStyleSheet('color:#a6e3a1;font-size:12px;')
        stats_layout.addWidget(self._lbl_repo)

        layout.addWidget(stats_frame)

        # --- Ostatni uruchomiony skrypt ---
        self._lbl_last_script = QLabel('')
        self._lbl_last_script.setStyleSheet('color:#89dceb;font-size:11px;padding:2px 4px;')
        self._lbl_last_script.hide()
        layout.addWidget(self._lbl_last_script)

        # --- Bufor ---
        buf_label = QLabel('Bufor (historia wpisów):')
        buf_label.setStyleSheet('color:#89b4fa;font-weight:bold;font-size:12px;')
        layout.addWidget(buf_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('border:none;background:#181825;')
        self._buf_container = QWidget()
        self._buf_layout = QVBoxLayout(self._buf_container)
        self._buf_layout.setContentsMargins(4, 4, 4, 4)
        self._buf_layout.setSpacing(2)
        self._buf_layout.addStretch()
        scroll.setWidget(self._buf_container)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(scroll)

        # --- Odśwież ręcznie ---
        refresh_btn = QPushButton('Odśwież')
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh(self) -> None:
        """Wczytuje snapshot z dysku (fallback gdy service nie jest dostępny)."""
        snap = load_snapshot(self._path)
        self.apply_snapshot(snap)
        self._badge_widget.setVisible(not is_hook_installed(self._path))

    def apply_snapshot(self, snap: ProjectSnapshot) -> None:
        """Aplikuje snapshot z SSMService — nie czyta z dysku."""
        self._lbl_round.setText(f'Runda: {snap.current_round or "—"}')
        self._lbl_session.setText(f'Sesja: {snap.session_count or "—"}')
        self._lbl_next.setText(f'Next: {snap.next_count}')
        self._lbl_done.setText(f'Done: {snap.done_count}')

        if snap.repo_name:
            self._lbl_repo.setText(f'Repo: {snap.repo_name}')

        if snap.last_event_timestamp:
            ts = snap.last_event_timestamp[:19].replace('T', ' ')
            self._lbl_last_event.setText(ts)

        if snap.last_script:
            self._lbl_last_script.setText(f'Ostatni skrypt: {snap.last_script}')
            self._lbl_last_script.show()
        else:
            self._lbl_last_script.hide()

        # Odśwież listę bufora
        while self._buf_layout.count() > 1:
            item = self._buf_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for entry in snap.buffer_entries:
            row = QLabel(self._format_buffer_entry(entry))
            row.setStyleSheet(
                f'color:{"#a6e3a1" if entry.status == "distributed" else "#f38ba8"};'
                'font-size:11px;padding:2px 4px;'
            )
            row.setWordWrap(True)
            self._buf_layout.insertWidget(self._buf_layout.count() - 1, row)

    def _format_buffer_entry(self, entry) -> str:
        status_icon = '✓' if entry.status == 'distributed' else '●'
        location = entry.distributed_to if entry.status == 'distributed' else 'PLAN.md'
        return f'{status_icon} [{entry.target}] {entry.content[:80]} → {location}'

    def _on_install_hook(self) -> None:
        result = install_hook(self._path)
        if result.success:
            self._badge_widget.hide()
