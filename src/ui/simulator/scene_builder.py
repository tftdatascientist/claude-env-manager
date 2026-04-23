"""Widget budowania sceny: tokeny uzytkownika/odpowiedzi + przyciski aktywnosci."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.simulator.models import ACTIVITY_REGISTRY, Activity, Scene


class _ActivityButton(QPushButton):
    """Przycisk aktywnosci: LPM inkrementuje count, PPM resetuje do 0."""

    def __init__(self, activity_id: str, parent=None) -> None:
        super().__init__(parent)
        self._id = activity_id
        self._count = 0
        self._def = ACTIVITY_REGISTRY[activity_id]
        self._refresh_label()
        self.clicked.connect(self._on_click)
        self.setFont(QFont("Consolas", 9))
        self.setFixedHeight(28)
        self._update_style()

    def _on_click(self) -> None:
        self._count += 1
        self._refresh_label()
        self._update_style()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._count = 0
            self._refresh_label()
            self._update_style()
        else:
            super().mousePressEvent(event)

    def _refresh_label(self) -> None:
        label = self._def.label
        if self._count > 0:
            self.setText(f"{label}  ×{self._count}")
        else:
            self.setText(label)

    def _update_style(self) -> None:
        if self._count > 0:
            self.setStyleSheet(
                "QPushButton { background-color: #094771; color: #ffffff; "
                "border: 1px solid #569cd6; border-radius: 3px; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #0e5a8a; }"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background-color: #2d2d2d; color: #cccccc; "
                "border: 1px solid #454545; border-radius: 3px; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #3c3c3c; }"
            )

    def get_count(self) -> int:
        return self._count

    def reset(self) -> None:
        self._count = 0
        self._refresh_label()
        self._update_style()


class SceneBuilder(QWidget):
    """
    Widget do budowania jednej sceny.

    Sygnaly:
        scene_ready(Scene) — uzytkownik kliknal 'Dodaj scene'
    """

    scene_ready = Signal(object)  # Scene

    # Grupy przyciskow aktywnosci (id → wyswietlana grupa)
    _GROUPS = [
        ("Pliki", ["file_read", "file_read_large", "file_edit", "file_write", "file_multi_read"]),
        ("Shell", ["bash_cmd", "bash_long", "grep_glob", "lint_run", "git_status"]),
        ("AI",    ["skill_invoke", "mcp_call", "subagent_launch"]),
        ("Web",   ["web_search", "web_fetch"]),
        ("Inne",  ["todo_read", "todo_write", "memory_read", "memory_write", "context_view"]),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._btns: dict[str, _ActivityButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # --- Tokeny ---
        tokens_row = QHBoxLayout()
        font_mono = QFont("Consolas", 9)

        tokens_row.addWidget(QLabel("User msg tok:"))
        self._user_tok = QSpinBox()
        self._user_tok.setRange(1, 100_000)
        self._user_tok.setValue(200)
        self._user_tok.setFont(font_mono)
        self._user_tok.setFixedWidth(90)
        tokens_row.addWidget(self._user_tok)

        tokens_row.addSpacing(16)
        tokens_row.addWidget(QLabel("Response tok:"))
        self._resp_tok = QSpinBox()
        self._resp_tok.setRange(1, 100_000)
        self._resp_tok.setValue(800)
        self._resp_tok.setFont(font_mono)
        self._resp_tok.setFixedWidth(90)
        tokens_row.addWidget(self._resp_tok)

        tokens_row.addSpacing(16)
        tokens_row.addWidget(QLabel("Nazwa sceny:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Scena")
        self._name_edit.setFont(font_mono)
        self._name_edit.setFixedWidth(150)
        tokens_row.addWidget(self._name_edit)

        tokens_row.addStretch()
        root.addLayout(tokens_row)

        # --- Przyciski aktywnosci w grupach ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(180)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        inner = QWidget()
        act_layout = QVBoxLayout(inner)
        act_layout.setSpacing(4)
        act_layout.setContentsMargins(0, 0, 0, 0)

        for group_name, ids in self._GROUPS:
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(f"{group_name}:")
            lbl.setFont(QFont("Consolas", 8))
            lbl.setStyleSheet("color: #569cd6;")
            lbl.setFixedWidth(42)
            row.addWidget(lbl)
            for act_id in ids:
                btn = _ActivityButton(act_id)
                self._btns[act_id] = btn
                row.addWidget(btn)
            row.addStretch()
            act_layout.addLayout(row)

        act_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # --- Aktywne (podglad) + przyciski akcji ---
        bottom_row = QHBoxLayout()
        self._active_label = QLabel("Aktywnosci: —")
        self._active_label.setFont(QFont("Consolas", 9))
        self._active_label.setStyleSheet("color: #b5cea8;")
        bottom_row.addWidget(self._active_label)
        bottom_row.addStretch()

        add_btn = QPushButton("+ Dodaj scene")
        add_btn.setFont(QFont("Consolas", 9))
        add_btn.setStyleSheet(
            "QPushButton { background-color: #007acc; color: white; "
            "border: none; border-radius: 3px; padding: 4px 14px; }"
            "QPushButton:hover { background-color: #1a8dd9; }"
        )
        add_btn.clicked.connect(self._emit_scene)
        bottom_row.addWidget(add_btn)

        clear_btn = QPushButton("Wyczysc")
        clear_btn.setFont(QFont("Consolas", 9))
        clear_btn.setStyleSheet(
            "QPushButton { background-color: #2d2d2d; color: #cccccc; "
            "border: 1px solid #454545; border-radius: 3px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #3c3c3c; }"
        )
        clear_btn.clicked.connect(self.clear)
        bottom_row.addWidget(clear_btn)

        root.addLayout(bottom_row)

        # Podpinamy update etykiety aktywnych do kazdego przycisku
        for btn in self._btns.values():
            btn.clicked.connect(self._update_active_label)

    def _update_active_label(self) -> None:
        active = [(aid, btn.get_count()) for aid, btn in self._btns.items() if btn.get_count() > 0]
        if active:
            parts = [f"{ACTIVITY_REGISTRY[aid].label} ×{cnt}" for aid, cnt in active]
            self._active_label.setText("Aktywnosci: " + ", ".join(parts))
        else:
            self._active_label.setText("Aktywnosci: —")

    def _emit_scene(self) -> None:
        activities = [
            Activity(activity_id=aid, count=btn.get_count())
            for aid, btn in self._btns.items()
            if btn.get_count() > 0
        ]
        name = self._name_edit.text().strip() or "Scena"
        scene = Scene(
            name=name,
            user_message_tokens=self._user_tok.value(),
            assistant_response_tokens=self._resp_tok.value(),
            activities=activities,
        )
        self.scene_ready.emit(scene)
        self.clear()

    def clear(self) -> None:
        for btn in self._btns.values():
            btn.reset()
        self._user_tok.setValue(200)
        self._resp_tok.setValue(800)
        self._name_edit.clear()
        self._active_label.setText("Aktywnosci: —")
