"""Wizard dialog for building PCC project files (CLAUDE/ARCHITECTURE/PLAN/CONVENTIONS)."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QWidget, QFormLayout, QComboBox, QLineEdit, QCheckBox, QScrollArea,
    QGroupBox, QDialogButtonBox, QFrame, QPlainTextEdit,
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

PLAN_STATUS_OPTIONS = ["active", "idle"]

ARCH_PATTERN_OPTIONS = [
    "MVC", "MVP", "MVVM", "layered", "event-driven",
    "pipeline", "plugin-based", "monolith", "microservices",
    "standalone script",
]

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
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
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
        for label, w in [("Nazwa:", self._name), ("Typ:", self._type), ("Klient:", self._client)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form.addRow(lbl, w)
        layout.addLayout(form)

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

        gb2, gb2_lay = _group("Key Files (jeden plik na linię: ścieżka: opis)")
        self._key_files = QPlainTextEdit()
        self._key_files.setPlaceholderText("src/main.py: punkt wejścia\nsrc/utils/helpers.py: narzędzia")
        self._key_files.setStyleSheet(_TEXTAREA)
        self._key_files.setFixedHeight(80)
        gb2_lay.addWidget(self._key_files)
        layout.addWidget(gb2)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        stack_items = [cb.text() for cb in self._stack_boxes if cb.isChecked()]
        key_files_lines = [l.strip() for l in self._key_files.toPlainText().splitlines() if l.strip()]
        stack_str = ", ".join(stack_items) if stack_items else "Python 3.13+"
        return {
            "project": {
                "name": self._name.text().strip(),
                "type": self._type.currentText(),
                "client": self._client.currentText(),
                "stack": stack_str,
            },
            "_stack_items": stack_items,
            "_key_files_items": key_files_lines,
        }


class ArchitectureTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        gb, gb_lay = _group("Overview — opis modułu/aplikacji")
        self._overview = QPlainTextEdit()
        self._overview.setPlaceholderText("Krótki opis czym jest ten projekt i co robi...")
        self._overview.setStyleSheet(_TEXTAREA)
        self._overview.setFixedHeight(60)
        gb_lay.addWidget(self._overview)
        layout.addWidget(gb)

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

        gb3, gb3_lay = _group("Components (jeden na linię: NazwaKomponentu: opis)")
        self._components = QPlainTextEdit()
        self._components.setPlaceholderText("Parser: rdzeń — parsowanie sekcji MD\nUIPanel: interfejs użytkownika PySide6")
        self._components.setStyleSheet(_TEXTAREA)
        self._components.setFixedHeight(80)
        gb3_lay.addWidget(self._components)
        layout.addWidget(gb3)

        gb4, gb4_lay = _group("External Dependencies (jeden na linię: pakiet: wersja)")
        self._ext_deps = QPlainTextEdit()
        self._ext_deps.setPlaceholderText("python: 3.13+\npytest: 8.2+\npydantic: 2.0+")
        self._ext_deps.setStyleSheet(_TEXTAREA)
        self._ext_deps.setFixedHeight(60)
        gb4_lay.addWidget(self._ext_deps)
        layout.addWidget(gb4)

        gb5, gb5_lay = _group("Constraints (jeden na linię)")
        self._constraints = QPlainTextEdit()
        self._constraints.setPlaceholderText("Brak zagnieżdżonych sekcji\nWyłącznie UTF-8")
        self._constraints.setStyleSheet(_TEXTAREA)
        self._constraints.setFixedHeight(50)
        gb5_lay.addWidget(self._constraints)
        layout.addWidget(gb5)

        gb6, gb6_lay = _group("Data Flow")
        self._data_flow = QPlainTextEdit()
        self._data_flow.setPlaceholderText("Wejście → Przetwarzanie → Wyjście")
        self._data_flow.setStyleSheet(_TEXTAREA)
        self._data_flow.setFixedHeight(50)
        gb6_lay.addWidget(self._data_flow)
        layout.addWidget(gb6)

        gb7, gb7_lay = _group("Decisions (jeden na linię: opis | YYYY-MM-DD | uzasadnienie)")
        self._decisions = QPlainTextEdit()
        self._decisions.setPlaceholderText("Użyto data_sources.query | 2026-04-24 | notion-client 3.0.0 usunął databases.query")
        self._decisions.setStyleSheet(_TEXTAREA)
        self._decisions.setFixedHeight(70)
        gb7_lay.addWidget(self._decisions)
        layout.addWidget(gb7)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        patterns = [cb.text() for cb in self._pattern_boxes if cb.isChecked()]
        components = [l.strip() for l in self._components.toPlainText().splitlines() if l.strip()]
        ext_deps = [l.strip() for l in self._ext_deps.toPlainText().splitlines() if l.strip()]
        constraints = [l.strip() for l in self._constraints.toPlainText().splitlines() if l.strip()]
        decisions = [l.strip() for l in self._decisions.toPlainText().splitlines() if l.strip()]
        return {
            "_overview": self._overview.toPlainText().strip(),
            "_patterns": patterns,
            "_components": components,
            "_ext_deps": ext_deps,
            "_constraints": constraints,
            "_data_flow": self._data_flow.toPlainText().strip(),
            "_decisions": decisions,
        }


class PlanTab(QWidget):
    """PCC v2.0 — meta / current / next / blockers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(6)
        self._status = _combo(PLAN_STATUS_OPTIONS, "active")
        self._goal = _input("cel bieżącej rundy")
        for label, w in [("Status:", self._status), ("Cel rundy:", self._goal)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form.addRow(lbl, w)
        layout.addLayout(form)

        gb, gb_lay = _group("Current — pierwsze zadanie rundy")
        self._current_task = _input("np. Zaimplementować parser MD")
        self._current_file = _input("np. src/parser.py (opcjonalnie)")
        for label, w in [("Zadanie:", self._current_task), ("Plik:", self._current_file)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_LABEL)
            form2 = QFormLayout()
            form2.addRow(lbl, w)
            gb_lay.addLayout(form2)
        layout.addWidget(gb)

        gb2, gb2_lay = _group("Next — kolejne zadania (jeden na linię)")
        self._next_tasks = QPlainTextEdit()
        self._next_tasks.setPlaceholderText("Napisać testy\nZrefaktorować moduł X\nCode review")
        self._next_tasks.setStyleSheet(_TEXTAREA)
        self._next_tasks.setFixedHeight(100)
        gb2_lay.addWidget(self._next_tasks)
        layout.addWidget(gb2)

        gb3, gb3_lay = _group("Blockers (opcjonalnie, jeden na linię)")
        self._blockers = QPlainTextEdit()
        self._blockers.setPlaceholderText("Czekam na decyzję architektoniczną\n...")
        self._blockers.setStyleSheet(_TEXTAREA)
        self._blockers.setFixedHeight(50)
        gb3_lay.addWidget(self._blockers)
        layout.addWidget(gb3)

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        next_lines = [l.strip() for l in self._next_tasks.toPlainText().splitlines() if l.strip()]
        blocker_lines = [l.strip() for l in self._blockers.toPlainText().splitlines() if l.strip()]
        return {
            "meta": {
                "status": self._status.currentText(),
                "goal": self._goal.text().strip(),
                "session": "1",
                "updated": now,
            },
            "_current_task": self._current_task.text().strip(),
            "_current_file": self._current_file.text().strip(),
            "_next_tasks": next_lines,
            "_blockers": blocker_lines,
        }


class ConventionsTab(QWidget):
    """CONVENTIONS.md — naming, file_layout, code_style, commit_style, testing, anti_patterns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        note = QLabel("Pola mają wartości domyślne dla Pythona. Zmień tylko to, co odbiega od standardu.")
        note.setStyleSheet("color: #5c6370; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        _DEFAULTS = {
            "naming": "snake_case dla plików i modułów Python\nPascalCase dla klas\nUPPER_CASE dla stałych modułowych",
            "file_layout": "src/ — kod źródłowy\ntests/ — testy pytest\ndocs/ — dokumentacja (opcjonalnie)",
            "code_style": "PEP 8, type hints (Python 3.12+)\nmax line 120 znaków\npathlib.Path zamiast os.path",
            "commit_style": "feat/fix/docs/refactor/test/chore",
            "testing": "pytest z tmp_path dla plików tymczasowych\nbrak hardkodowanych ścieżek w testach",
            "anti_patterns": "nie hardkoduj ścieżek absolutnych\nnie pomijaj type hints\nnie używaj os.path (używaj pathlib.Path)",
        }

        self._fields: dict[str, QPlainTextEdit] = {}
        labels = {
            "naming": "Naming (jeden punkt na linię)",
            "file_layout": "File Layout (jeden punkt na linię)",
            "code_style": "Code Style (jeden punkt na linię)",
            "commit_style": "Commit Style (jeden punkt na linię)",
            "testing": "Testing (jeden punkt na linię)",
            "anti_patterns": "Anti-patterns (jeden punkt na linię)",
        }
        for key, title in labels.items():
            gb, gb_lay = _group(title)
            te = QPlainTextEdit(_DEFAULTS[key])
            te.setStyleSheet(_TEXTAREA)
            te.setFixedHeight(60)
            gb_lay.addWidget(te)
            layout.addWidget(gb)
            self._fields[key] = te

        layout.addStretch()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(_scrolled(inner))
        self.layout().setContentsMargins(4, 4, 4, 4)

    def get_overrides(self) -> dict:
        return {
            key: [l.strip() for l in te.toPlainText().splitlines() if l.strip()]
            for key, te in self._fields.items()
        }


# ---------------------------------------------------------------------------
# Wizard Dialog
# ---------------------------------------------------------------------------

class ProjectWizardDialog(QDialog):
    """Multi-tab wizard for building all 4 PCC project files."""

    def __init__(self, project_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kreator plików projektu — PCC")
        self.setMinimumSize(640, 560)
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
        self._arch_tab = ArchitectureTab()
        self._plan_tab = PlanTab()
        self._conventions_tab = ConventionsTab()

        self._tabs.addTab(self._claude_tab, "CLAUDE.md")
        self._tabs.addTab(self._arch_tab, "ARCHITECTURE.md")
        self._tabs.addTab(self._plan_tab, "PLAN.md")
        self._tabs.addTab(self._conventions_tab, "CONVENTIONS.md")

        if project_name:
            self._claude_tab._name.setText(project_name)

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
            "ARCHITECTURE.md": self._arch_tab.get_overrides(),
            "PLAN.md": self._plan_tab.get_overrides(),
            "CONVENTIONS.md": self._conventions_tab.get_overrides(),
        }
        self.accept()

    @property
    def result_data(self) -> dict[str, dict] | None:
        return self._result


# ---------------------------------------------------------------------------
# Helper: convert wizard result to create_from_template overrides
# ---------------------------------------------------------------------------

def build_overrides(file_data: dict, fname: str) -> dict:
    """Convert raw wizard data for one file into overrides for create_from_template."""
    overrides: dict = {}

    if fname == "CLAUDE.md":
        overrides["project"] = file_data["project"]
        if file_data.get("_stack_items"):
            overrides["stack"] = file_data["_stack_items"]
        if file_data.get("_key_files_items"):
            overrides["key_files"] = file_data["_key_files_items"]

    elif fname == "ARCHITECTURE.md":
        overview = file_data.get("_overview", "")
        patterns = file_data.get("_patterns", [])
        components = file_data.get("_components", [])
        ext_deps = file_data.get("_ext_deps", [])
        constraints = file_data.get("_constraints", [])
        decisions = file_data.get("_decisions", [])
        data_flow = file_data.get("_data_flow", "")

        if overview or patterns:
            combined = overview
            if patterns:
                combined += ("\n" if combined else "") + "Wzorce: " + ", ".join(patterns)
            overrides["overview"] = combined
        if components:
            overrides["components"] = components
        if ext_deps:
            overrides["external_deps"] = ext_deps
        if constraints:
            overrides["constraints"] = constraints
        if data_flow:
            overrides["data_flow"] = data_flow
        if decisions:
            overrides["decisions"] = decisions

    elif fname == "PLAN.md":
        overrides["meta"] = file_data["meta"]
        current_task = file_data.get("_current_task", "")
        current_file = file_data.get("_current_file", "")
        if current_task:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            overrides["current"] = {
                "task": current_task,
                "file": current_file,
                "started": now,
            }
        next_tasks = file_data.get("_next_tasks", [])
        if next_tasks:
            overrides["next"] = [{"done": False, "text": t, "date": ""} for t in next_tasks]
        blockers = file_data.get("_blockers", [])
        if blockers:
            overrides["blockers"] = blockers

    elif fname == "CONVENTIONS.md":
        for section in ("naming", "file_layout", "code_style", "commit_style", "testing"):
            items = file_data.get(section, [])
            if items:
                overrides[section] = items
        anti = file_data.get("anti_patterns", [])
        if anti:
            overrides["anti_patterns"] = [{"done": False, "text": t, "date": ""} for t in anti]

    return overrides
