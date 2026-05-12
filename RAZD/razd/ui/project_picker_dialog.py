from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from razd.notion.projects_fetcher import NotionProject

logger = logging.getLogger(__name__)

_SLOT_COLORS = ["#7C3AED", "#0EA5E9", "#10B981", "#F59E0B"]


@dataclass
class ProjectSelection:
    is_custom: bool
    notion_project: NotionProject | None = None
    custom_name: str | None = None

    @classmethod
    def custom(cls, name: str) -> ProjectSelection:
        return cls(is_custom=True, custom_name=name or "Custom")

    @classmethod
    def from_notion(cls, project: NotionProject) -> ProjectSelection:
        return cls(is_custom=False, notion_project=project)

    def display_name(self) -> str:
        if self.is_custom:
            return f"[Custom] {self.custom_name or 'Projekt nieokreślony'}"
        if self.notion_project:
            return self.notion_project.name
        return "Brak projektu"


class _ProjectButton(QPushButton):
    """Przycisk reprezentujący jeden pinned projekt."""

    def __init__(self, slot: int, color: str, project, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project   # NotionProjectRow
        self._color = color
        self._slot = slot

        name = project.name if project else f"Slot {slot} — pusty"
        meta_parts = []
        if project and project.due_date:
            meta_parts.append(f"do {project.due_date}")
        if project and project.status:
            meta_parts.append(project.status)
        meta = "  ·  ".join(meta_parts)

        self.setText(f"{name}\n{meta}" if meta else name)
        self.setEnabled(bool(project))
        self.setMinimumHeight(56)
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background: #1a1a1a;"
            f"  border: 1px solid {color}55;"
            f"  border-left: 4px solid {color};"
            f"  border-radius: 6px;"
            f"  color: #eee;"
            f"  font-size: 12px;"
            f"  font-weight: bold;"
            f"  text-align: left;"
            f"  padding: 6px 14px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: #222;"
            f"  border-color: {color}cc;"
            f"  border-left: 4px solid {color};"
            f"}}"
            f"QPushButton:pressed {{ background: #1e1e2e; }}"
            f"QPushButton:disabled {{"
            f"  border: 1px solid #222;"
            f"  border-left: 4px solid #333;"
            f"  color: #333;"
            f"}}"
        )

    @property
    def project(self):
        return self._project


class ProjectPickerDialog(QDialog):
    """Dialog wyboru projektu przed Focus Sessionem.

    Pokazuje wyłącznie 4 pinnowane projekty priorytetowe + opcję Custom.
    Brak pinnowanych projektów = slot wyświetlony jako wyszarzony.
    """

    def __init__(
        self,
        fetcher=None,          # nieużywany — zostawiony dla kompatybilności sygnatur
        repo=None,             # RazdRepository | None
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAZD — Focus Timer")
        self.setMinimumSize(440, 360)
        self.setMaximumSize(560, 480)
        self.setWindowModality(Qt.ApplicationModal)

        self._repo = repo
        self._selection: ProjectSelection | None = None

        self._pinned: list[tuple[int, object, str]] = []  # (slot, NotionProjectRow, color)
        self._load_pinned()
        self._build_ui()

    def _load_pinned(self) -> None:
        if self._repo is None:
            return
        try:
            self._pinned = self._repo.get_pinned_projects()
        except Exception:
            pass

    def selection(self) -> ProjectSelection | None:
        return self._selection

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 14, 16, 14)

        header = QLabel("Wybierz projekt focus:")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #ddd;")
        root.addWidget(header)

        # wyszukiwanie — filtruje na żywo po nazwach przycisków
        self._search = QLineEdit()
        self._search.setPlaceholderText("Szukaj w projektach priorytetowych...")
        self._search.textChanged.connect(self._filter)
        self._search.setStyleSheet(
            "QLineEdit { background: #1e1e1e; border: 1px solid #333; border-radius: 4px;"
            " padding: 4px 8px; color: #ddd; font-size: 11px; }"
        )
        root.addWidget(self._search)

        # ── 4 przyciski projektów ────────────────────────────────────────
        pinned_by_slot: dict[int, tuple[object, str]] = {
            slot: (proj, color) for slot, proj, color in self._pinned
        }

        self._proj_btns: list[_ProjectButton] = []
        for i in range(4):
            slot = i + 1
            color = _SLOT_COLORS[i]
            proj, c = pinned_by_slot.get(slot, (None, color))
            btn = _ProjectButton(slot, c, proj)
            btn.clicked.connect(lambda checked=False, b=btn: self._select_project(b.project))
            self._proj_btns.append(btn)
            root.addWidget(btn)

        # ── separator ────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #2a2a2a;")
        root.addWidget(sep)

        # ── custom row ───────────────────────────────────────────────────
        custom_row = QHBoxLayout()
        custom_row.setSpacing(6)
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("Nazwa własna (opcjonalnie)...")
        self._custom_input.setStyleSheet(
            "QLineEdit { background: #1e1e1e; border: 1px solid #333; border-radius: 4px;"
            " padding: 3px 8px; color: #ddd; font-size: 11px; }"
        )
        custom_row.addWidget(self._custom_input, 1)
        btn_custom = QPushButton("Start bez projektu")
        btn_custom.setStyleSheet(
            "QPushButton { color: #777; font-size: 11px; padding: 4px 10px;"
            " background: #1a1a1a; border: 1px solid #333; border-radius: 4px; }"
            "QPushButton:hover { border-color: #555; color: #aaa; }"
        )
        btn_custom.clicked.connect(self._select_custom)
        custom_row.addWidget(btn_custom)
        root.addLayout(custom_row)

        # anuluj
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.setStyleSheet("color: #555; font-size: 10px; padding: 3px 10px;")
        btn_cancel.clicked.connect(self.reject)
        cancel_row.addWidget(btn_cancel)
        root.addLayout(cancel_row)

    def _filter(self, text: str) -> None:
        q = text.lower()
        for btn in self._proj_btns:
            if btn.project is None:
                continue
            visible = q in btn.project.name.lower()
            btn.setVisible(visible)

    def _select_project(self, project) -> None:
        if project is None:
            return
        # budujemy NotionProject DTO z NotionProjectRow
        from razd.notion.projects_fetcher import NotionProject
        notion_proj = NotionProject(
            notion_page_id=project.notion_page_id,
            name=project.name,
            status=project.status,
            priority=project.priority,
            due_date=project.due_date,
        )
        self._selection = ProjectSelection.from_notion(notion_proj)
        self.accept()

    def _select_custom(self) -> None:
        name = self._custom_input.text().strip()
        self._selection = ProjectSelection.custom(name)
        self.accept()
