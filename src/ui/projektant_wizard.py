"""Wizard dialog for building Projektant CC project files via dropdowns and checkboxes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QWidget, QFormLayout, QComboBox, QLineEdit, QCheckBox, QScrollArea,
    QGroupBox, QDialogButtonBox, QFrame, QPlainTextEdit, QSizePolicy,
)

# ---------------------------------------------------------------------------
# Static option lists
# ---------------------------------------------------------------------------

PROJECT_TYPES = [
    "", "web app", "API", "moduł aplikacji", "biblioteka", "CLI tool",
    "desktop app", "skrypt automatyzacji", "pipeline danych", "dokumentacja",
    "research / prototyp", "integracja zewnętrzna",
]

CLIENT_OPTIONS = ["", "własny", "klient komercyjny", "open source", "wewnętrzny"]

REPO_OPTIONS = ["", "lokalne", "GitHub", "GitHub (prywatne)", "GitLab", "brak"]

STACK_OPTIONS = [
    "Python 3.13", "Python 3.12", "Python 3.11",
    "PySide6 (Qt6)", "PyQt6",
    "FastAPI", "Flask", "Django",
    "React", "Vue", "Next.js", "Svelte",
    "TypeScript", "JavaScript",
    "Node.js", "Bun",
    "PostgreSQL", "SQLite", "MySQL", "MongoDB", "Redis",
    "Docker", "docker-compose",
    "pytest", "unittest",
    "Notion API", "OpenAI API", "Anthropic API",
    "watchdog", "pydantic", "SQLAlchemy",
    "Markdown", "Regex",
    "pywin32", "pathlib",
]

PLAN_STATUS_OPTIONS = ["active", "on hold", "done", "cancelled"]

ARCH_PATTERN_OPTIONS = [
    "MVC", "MVP", "MVVM", "layered", "event-driven",
    "pipeline", "plugin-based", "monolith", "microservices",
    "standalone script",
]

CURRENT_STATE_OPTIONS = [
    "in progress", "blocked", "waiting for review",
    "waiting for input", "done", "not started",
]

BLOCKER_OPTIONS = ["none", "brak zasobów", "zależność zewnętrzna", "decyzja architektoniczna", "inne"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LABEL = "color: #abb2bf; font-size: 11px;"
_GROUP = (
    "QGroupBox { color: #e5c07b; font-size: 11px; font-weight: bold;"
    " border: 1px solid #3e4451; border-radius: 4px; margin-top: 8px; padding-top: 6px; }"
    "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
)
_COMBO = (
    "QComboBox { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
    " border-radius: 3px; padding: 3px 6px; font-size: 11px; }"
    "QComboBox::drop-down { border: none; width: 18px; }"
    "QComboBox QAbstractItemView { background: #21252b; color: #abb2bf;"
    " selection-background-color: #3e4451; selection-color: #e5c07b; }"
)
_INPUT = (
    "QLineEdit { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
    " border-radius: 3px; padding: 3px 6px; font-size: 11px; }"
)
_TEXTAREA = (
    "QPlainTextEdit { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
    " border-radius: 3px; font-size: 11px; }"
)
_CHECK = "QCheckBox { color: #abb2bf; font-size: 11px; } QCheckBox::indicator { width: 13px; height: 13px; }"
_BTN = (
    "QPushButton { background: #3e4451; color: #abb2bf; border: 1px solid #4b5263;"
    " border-radius: 3px; padding: 4px 12px; font-size: 11px; }"
    "QPushButton:hover { background: #4b5263; color: #e5c07b; }"
)
_BTN_OK = (
    "QPushButton { background: #2d4a2d; color: #98c379; border: 1px solid #3a5c3a;"
    " border-radius: 3px; padding: 4px 14px; font-size: 11px; font-weight: bold; }"
    "QPushButton:hover { background: #3a5c3a; }"
)


def _combo(options: list[str], default: str = "") -> QComboBox:
    cb = QComboBox()
    cb.addItems(options)
    cb.setStyleSheet(_COMBO)
    if default in options:
        cb.setCurrentText(default)
    return cb


def _input(placeholder: str = "", value: str = "") -> QLineEdit:
    w = QLineEdit(value)
    w.setPlaceholderText(placeholder)
    w.setStyleSheet(_INPUT)
    return w


def _scrolled(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(inner)
    sa.setStyleSheet("QScrollArea { border: none; background: transparent; }")
    return sa


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #3e4451;")
    return f


def _group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    gb = QGroupBox(title)
    gb.setStyleSheet(_GROUP)
    lay = QVBoxLayout(gb)
    lay.setSpacing(4)
    return gb, lay


def _checkboxes(options: list[str], checked: list[str] | None = None) -> tuple[QWidget, list[QCheckBox]]:
    """Return a widget with a grid of checkboxes and the checkbox objects."""
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    boxes: list[QCheckBox] = []
    for opt in options:
        cb = QCheckBox(opt)
        cb.setStyleSheet(_CHECK)
        if checked and opt in checked:
            cb.setChecked(True)
        layout.addWidget(cb)
    boxes = [w.layout().itemAt(i).widget() for i in range(w.layout().count())]
    return w, boxes  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Per-file tab widgets
# ---------------------------------------------------------------------------

class ClaudeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(6)
        self._name = _input("np. Mój Projekt")
        self._type = _combo(PROJECT_TYPES)
        self._client = _combo(CLIENT_OPTIONS)
        self._repo = _combo(REPO_OPTIONS)
        for label, w in [("Nazwa:", self._name), ("Typ:", self._type),
                         ("Klient:", self._client), ("Repo:", self._repo)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form.addRow(lbl, w)
        layout.addLayout(form)

        # Stack checkboxes
        gb, gb_lay = _group("Stack (zaznacz używane technologie)")
        _, self._stack_boxes = _checkboxes(STACK_OPTIONS)
        stack_w = QWidget()
        stack_lay = QVBoxLayout(stack_w)
        stack_lay.setContentsMargins(0, 0, 0, 0)
        stack_lay.setSpacing(2)
        for cb in self._stack_boxes:
            stack_lay.addWidget(cb)
        gb_lay.addWidget(stack_w)
        layout.addWidget(gb)

        # Key files — freetext list
        gb2, gb2_lay = _group("Key Files (jeden plik na linię: ścieżka: opis)")
        self._key_files = QPlainTextEdit()
        self._key_files.setPlaceholderText("src/main.py: punkt wejścia\nsrc/utils/helpers.py: narzędzia")
        self._key_files.setStyleSheet(_TEXTAREA)
        self._key_files.setFixedHeight(80)
        gb2_lay.addWidget(self._key_files)
        layout.addWidget(gb2)

        # Specifics — freetext list
        gb3, gb3_lay = _group("Specifics (jeden punkt na linię)")
        self._specifics = QPlainTextEdit()
        self._specifics.setPlaceholderText("Brak zagnieżdżonych sekcji\nParser działa standalone i jako import")
        self._specifics.setStyleSheet(_TEXTAREA)
        self._specifics.setFixedHeight(70)
        gb3_lay.addWidget(self._specifics)
        layout.addWidget(gb3)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        stack_items = [cb.text() for cb in self._stack_boxes if cb.isChecked()]
        key_files_lines = [l.strip() for l in self._key_files.toPlainText().splitlines() if l.strip()]
        specifics_lines = [l.strip() for l in self._specifics.toPlainText().splitlines() if l.strip()]
        return {
            "project": {
                "name": self._name.text().strip(),
                "type": self._type.currentText(),
                "client": self._client.currentText(),
                "repo": self._repo.currentText(),
            },
            "_stack_items": stack_items,
            "_key_files_items": key_files_lines,
            "_specifics_items": specifics_lines,
        }


class StatusTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(6)
        self._project = _input("nazwa projektu")
        self._plan = _combo(["none", "active", "on hold", "done"])

        for label, w in [("Projekt:", self._project), ("Plan:", self._plan)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form.addRow(lbl, w)
        layout.addLayout(form)

        # Current section
        gb, gb_lay = _group("Current — aktualny stan")
        form2 = QFormLayout()
        form2.setSpacing(6)
        self._task = _input("co teraz robisz")
        self._files = _input("src/foo.py, src/bar.py")
        self._state = _combo(CURRENT_STATE_OPTIONS, "in progress")
        self._blocker = _combo(BLOCKER_OPTIONS, "none")
        self._next_step = _input("następny krok")
        for label, w in [("Task:", self._task), ("Files:", self._files),
                         ("State:", self._state), ("Blocker:", self._blocker),
                         ("Next step:", self._next_step)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form2.addRow(lbl, w)
        gb_lay.addLayout(form2)
        layout.addWidget(gb)

        # Next tasks
        gb2, gb2_lay = _group("Next — zadania do zrobienia (jeden na linię)")
        self._next_tasks = QPlainTextEdit()
        self._next_tasks.setPlaceholderText("Napisać testy\nDodać walidację\nRefaktor modułu X")
        self._next_tasks.setStyleSheet(_TEXTAREA)
        self._next_tasks.setFixedHeight(80)
        gb2_lay.addWidget(self._next_tasks)
        layout.addWidget(gb2)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        next_items = [
            {"done": False, "text": l.strip(), "date": ""}
            for l in self._next_tasks.toPlainText().splitlines() if l.strip()
        ]
        return {
            "meta": {
                "project": self._project.text().strip(),
                "session": "1",
                "updated": now,
                "plan": self._plan.currentText(),
            },
            "current": {
                "task": self._task.text().strip(),
                "files": self._files.text().strip(),
                "state": self._state.currentText(),
                "blocker": self._blocker.currentText(),
                "next_step": self._next_step.text().strip(),
            },
            "_next_items": next_items,
        }


class ArchitectureTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        # Overview
        gb, gb_lay = _group("Overview — opis modułu/aplikacji")
        self._overview = QPlainTextEdit()
        self._overview.setPlaceholderText("Krótki opis czym jest ten projekt i co robi...")
        self._overview.setStyleSheet(_TEXTAREA)
        self._overview.setFixedHeight(60)
        gb_lay.addWidget(self._overview)
        layout.addWidget(gb)

        # Architecture pattern
        gb2, gb2_lay = _group("Wzorzec architektoniczny")
        _, self._pattern_boxes = _checkboxes(ARCH_PATTERN_OPTIONS)
        pat_w = QWidget()
        pat_lay = QVBoxLayout(pat_w)
        pat_lay.setContentsMargins(0, 0, 0, 0)
        pat_lay.setSpacing(2)
        for cb in self._pattern_boxes:
            pat_lay.addWidget(cb)
        gb2_lay.addWidget(pat_w)
        layout.addWidget(gb2)

        # Components
        gb3, gb3_lay = _group("Components (jeden na linię: nazwa: opis)")
        self._components = QPlainTextEdit()
        self._components.setPlaceholderText("parser.py: rdzeń — parsowanie sekcji\nui/panel.py: interfejs użytkownika")
        self._components.setStyleSheet(_TEXTAREA)
        self._components.setFixedHeight(80)
        gb3_lay.addWidget(self._components)
        layout.addWidget(gb3)

        # Data flow
        gb4, gb4_lay = _group("Data Flow (opis przepływu danych)")
        self._data_flow = QPlainTextEdit()
        self._data_flow.setPlaceholderText("Wejście → Przetwarzanie → Wyjście")
        self._data_flow.setStyleSheet(_TEXTAREA)
        self._data_flow.setFixedHeight(60)
        gb4_lay.addWidget(self._data_flow)
        layout.addWidget(gb4)

        # Decisions
        gb5, gb5_lay = _group("Decisions (jeden na linię)")
        self._decisions = QPlainTextEdit()
        self._decisions.setPlaceholderText("Użyto X zamiast Y, bo...\nBrak zagnieżdżeń — regex nie obsługuje rekurencji")
        self._decisions.setStyleSheet(_TEXTAREA)
        self._decisions.setFixedHeight(70)
        gb5_lay.addWidget(self._decisions)
        layout.addWidget(gb5)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        patterns = [cb.text() for cb in self._pattern_boxes if cb.isChecked()]
        components = [l.strip() for l in self._components.toPlainText().splitlines() if l.strip()]
        decisions = [l.strip() for l in self._decisions.toPlainText().splitlines() if l.strip()]
        return {
            "_overview": self._overview.toPlainText().strip(),
            "_patterns": patterns,
            "_components": components,
            "_data_flow": self._data_flow.toPlainText().strip(),
            "_decisions": decisions,
        }


class PlanTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(6)
        self._status = _combo(PLAN_STATUS_OPTIONS, "active")
        self._goal = _input("cel planu / co chcemy osiągnąć")
        for label, w in [("Status:", self._status), ("Cel:", self._goal)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form.addRow(lbl, w)
        layout.addLayout(form)

        # Steps
        gb, gb_lay = _group("Steps — kroki planu (jeden na linię)")
        self._steps = QPlainTextEdit()
        self._steps.setPlaceholderText("Zaprojektować API\nNapisać testy\nZaimplementować parser\nCode review")
        self._steps.setStyleSheet(_TEXTAREA)
        self._steps.setFixedHeight(120)
        gb_lay.addWidget(self._steps)
        layout.addWidget(gb)

        # Notes
        gb2, gb2_lay = _group("Notes (opcjonalne)")
        self._notes = QPlainTextEdit()
        self._notes.setPlaceholderText("Dodatkowe uwagi, ograniczenia, kontekst...")
        self._notes.setStyleSheet(_TEXTAREA)
        self._notes.setFixedHeight(60)
        gb2_lay.addWidget(self._notes)
        layout.addWidget(gb2)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        steps = [
            {"done": False, "text": l.strip(), "date": ""}
            for l in self._steps.toPlainText().splitlines() if l.strip()
        ]
        return {
            "meta": {
                "status": self._status.currentText(),
                "goal": self._goal.text().strip(),
                "session": "1",
                "updated": now,
            },
            "_steps": steps,
            "_notes": self._notes.toPlainText().strip(),
        }


class ChangelogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        lbl = QLabel("CHANGELOG.md nie wymaga wypełnienia przy tworzeniu projektu.\nWpisy są dodawane w trakcie pracy.")
        lbl.setStyleSheet("color: #5c6370; font-size: 11px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        gb, gb_lay = _group("Opcjonalny wpis startowy")
        self._entry = QPlainTextEdit()
        self._entry.setPlaceholderText("np. Inicjalizacja projektu")
        self._entry.setStyleSheet(_TEXTAREA)
        self._entry.setFixedHeight(60)
        gb_lay.addWidget(self._entry)
        layout.addWidget(gb)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        return {"_entry": self._entry.toPlainText().strip()}


# ---------------------------------------------------------------------------
# Wizard Dialog
# ---------------------------------------------------------------------------

class ProjectWizardDialog(QDialog):
    """Multi-tab wizard for building all 5 Projektant CC project files."""

    def __init__(self, project_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kreator plików projektu — Projektant CC")
        self.setMinimumSize(620, 540)
        self.setModal(True)
        self._result: dict[str, dict] | None = None
        self._setup_ui(project_name)

    def _setup_ui(self, project_name: str) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        title = QLabel("Wypełnij pola dla każdego pliku. Puste pola zostaną pominięte.")
        title.setStyleSheet("color: #5c6370; font-size: 11px;")
        root.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #3e4451; }"
            "QTabBar::tab { background: #21252b; color: #abb2bf; padding: 5px 14px;"
            " border: 1px solid #3e4451; border-bottom: none; font-size: 11px; }"
            "QTabBar::tab:selected { background: #2c313a; color: #e5c07b; }"
            "QTabBar::tab:hover { background: #2c313a; }"
        )

        self._claude_tab = ClaudeTab()
        self._status_tab = StatusTab()
        self._arch_tab = ArchitectureTab()
        self._plan_tab = PlanTab()
        self._changelog_tab = ChangelogTab()

        self._tabs.addTab(self._claude_tab, "CLAUDE.md")
        self._tabs.addTab(self._status_tab, "STATUS.md")
        self._tabs.addTab(self._arch_tab, "ARCHITECTURE.md")
        self._tabs.addTab(self._plan_tab, "PLAN.md")
        self._tabs.addTab(self._changelog_tab, "CHANGELOG.md")

        # Pre-fill project name if provided
        if project_name:
            self._claude_tab._name.setText(project_name)
            self._status_tab._project.setText(project_name)

        root.addWidget(self._tabs, 1)

        root.addWidget(_sep())

        buttons = QDialogButtonBox()
        btn_ok = buttons.addButton("Utwórz pliki", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_ok.setStyleSheet(_BTN_OK)
        btn_cancel = buttons.addButton("Anuluj", QDialogButtonBox.ButtonRole.RejectRole)
        btn_cancel.setStyleSheet(_BTN)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        self._result = {
            "CLAUDE.md": self._claude_tab.get_overrides(),
            "STATUS.md": self._status_tab.get_overrides(),
            "ARCHITECTURE.md": self._arch_tab.get_overrides(),
            "PLAN.md": self._plan_tab.get_overrides(),
            "CHANGELOG.md": self._changelog_tab.get_overrides(),
        }
        self.accept()

    @property
    def result_data(self) -> dict[str, dict] | None:
        return self._result


# ---------------------------------------------------------------------------
# Helper: convert wizard result to create_from_template overrides
# ---------------------------------------------------------------------------

def build_overrides(file_data: dict, fname: str) -> dict:
    """
    Convert raw wizard data for one file into overrides dict
    suitable for create_from_template(..., overrides=...).
    """
    from src.projektant.template_parser import build_list

    overrides: dict = {}

    if fname == "CLAUDE.md":
        overrides["project"] = file_data["project"]
        if file_data.get("_stack_items"):
            overrides["stack"] = file_data["_stack_items"]
        if file_data.get("_key_files_items"):
            overrides["key_files"] = file_data["_key_files_items"]
        if file_data.get("_specifics_items"):
            overrides["specifics"] = file_data["_specifics_items"]

    elif fname == "STATUS.md":
        overrides["meta"] = file_data["meta"]
        overrides["current"] = file_data["current"]
        if file_data.get("_next_items"):
            overrides["next"] = file_data["_next_items"]

    elif fname == "ARCHITECTURE.md":
        overview = file_data.get("_overview", "")
        patterns = file_data.get("_patterns", [])
        components = file_data.get("_components", [])
        data_flow = file_data.get("_data_flow", "")
        decisions = file_data.get("_decisions", [])

        if overview or patterns:
            combined = overview
            if patterns:
                combined += ("\n" if combined else "") + "Wzorce: " + ", ".join(patterns)
            overrides["overview"] = combined
        if components:
            overrides["components"] = components
        if data_flow:
            overrides["data_flow"] = data_flow
        if decisions:
            overrides["decisions"] = decisions

    elif fname == "PLAN.md":
        overrides["meta"] = file_data["meta"]
        if file_data.get("_steps"):
            overrides["steps"] = file_data["_steps"]
        if file_data.get("_notes"):
            overrides["notes"] = file_data["_notes"]

    elif fname == "CHANGELOG.md":
        entry = file_data.get("_entry", "")
        if entry:
            today = datetime.now().strftime("%Y-%m-%d")
            overrides["entries"] = [{"done": False, "text": entry, "date": today}]

    return overrides
