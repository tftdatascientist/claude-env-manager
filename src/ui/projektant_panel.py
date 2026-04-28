"""Projektant panel — PLAN.md i pliki PCC z widokiem diff i sekcjami semantycznymi."""

from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from src.projektant.template_parser import (
    build_dict, build_list, create_from_template, parse_dict, parse_list,
    read_file, read_section, write_section,
)
from src.ui.projektant_wizard import ProjectWizardDialog, build_overrides
from src.ui.ai_project_wizard import AIProjectWizardDialog
from src.models.history import load_history
from src.utils.paths import user_history_path
from src.utils.aliases import load_aliases
from src.utils.relocations import resolve_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_FILES = ["CLAUDE.md", "ARCHITECTURE.md", "PLAN.md", "CONVENTIONS.md"]

_SECTION_RE = re.compile(
    r"<!--\s*SECTION:(\w+)\s*-->(?P<body>.*?)<!--\s*/SECTION:\w+\s*-->",
    re.DOTALL,
)

STATUS_COLORS = {
    "active": "#98c379",
    "done":   "#61afef",
    "paused": "#e5c07b",
    "idle":   "#5c6370",
    "draft":  "#abb2bf",
}

_SECTION_NAME_LABELS: dict[str, str] = {
    "meta": "Meta planu", "current": "Stan rundy", "next": "Następne kroki",
    "done": "Ukończone", "blockers": "Blokery", "session_log": "Dziennik sesji",
    "project": "Projekt", "stack": "Stack", "key_files": "Kluczowe pliki",
    "overview": "Przegląd", "components": "Komponenty",
    "external_deps": "Zależności zewnętrzne", "constraints": "Ograniczenia",
    "data_flow": "Przepływ danych", "decisions": "Decyzje",
    "naming": "Nazewnictwo", "file_layout": "Struktura plików",
    "code_style": "Styl kodu", "commit_style": "Styl commitów",
    "testing": "Testowanie", "anti_patterns": "Antywzorce",
}

_S = {
    "label": "color:#abb2bf;font-size:11px;padding:2px 0;",
    "title": "color:#e5c07b;font-size:11px;font-weight:bold;padding:2px 0;",
    "btn":   ("QPushButton{background:#3e4451;color:#abb2bf;border:1px solid #4b5263;"
              "border-radius:3px;padding:3px 10px;font-size:11px;}"
              "QPushButton:hover{background:#4b5263;color:#e5c07b;}"
              "QPushButton:disabled{color:#5c6370;}"),
    "save":  ("QPushButton{background:#2d4a2d;color:#98c379;border:1px solid #3a5c3a;"
              "border-radius:3px;padding:3px 12px;font-size:11px;font-weight:bold;}"
              "QPushButton:hover{background:#3a5c3a;}"),
    "new":   ("QPushButton{background:#2d3a4a;color:#61afef;border:1px solid #3a4a5c;"
              "border-radius:3px;padding:4px 10px;font-size:11px;font-weight:bold;}"
              "QPushButton:hover{background:#3a4a5c;color:#56b6c2;}"),
    "create":("QPushButton{background:#2d4a2d;color:#98c379;border:1px solid #3a5c3a;"
              "border-radius:3px;padding:4px 10px;font-size:11px;}"
              "QPushButton:hover{background:#3a5c3a;}"
              "QPushButton:disabled{color:#5c6370;background:#1e2127;border-color:#2c313a;}"),
    "discard":("QPushButton{background:#4a2d2d;color:#e06c75;border:1px solid #5c3a3a;"
               "border-radius:3px;padding:3px 12px;font-size:11px;}"
               "QPushButton:hover{background:#5c3a3a;}"),
    "editor": ("QPlainTextEdit{background:#1e2127;color:#abb2bf;border:1px solid #3e4451;}"
               "QPlainTextEdit:focus{border-color:#61afef;}"),
    "combo":  ("QComboBox{background:#21252b;color:#abb2bf;border:1px solid #3e4451;"
               "border-radius:3px;padding:3px 6px;font-size:11px;}"
               "QComboBox::drop-down{border:none;width:20px;}"
               "QComboBox QAbstractItemView{background:#21252b;color:#abb2bf;"
               "selection-background-color:#3e4451;selection-color:#e5c07b;}"),
    "list":   ("QListWidget{background:#21252b;color:#abb2bf;border:1px solid #3e4451;font-size:12px;}"
               "QListWidget::item{padding:4px 8px;}"
               "QListWidget::item:selected{background:#3e4451;color:#e5c07b;}"
               "QListWidget::item:hover{background:#2c313a;}"),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_section_role(name: str, body: str) -> str:
    """Rozpoznaje rolę sekcji na podstawie ZAWARTOŚCI (nie tylko nazwy)."""
    b = body.strip()
    # Stan rundy — sekcja z polem task i started
    if re.search(r"^-\s*task\s*:", b, re.MULTILINE) and re.search(r"^-\s*started\s*:", b, re.MULTILINE):
        return "Stan rundy"
    # Meta planu — status + goal + session
    if re.search(r"^-\s*status\s*:", b, re.MULTILINE) and re.search(r"^-\s*goal\s*:", b, re.MULTILINE):
        return "Meta planu"
    # Decyzje — checkboxy z numerem i datą autora (PRZED ogólną detekcją checklist)
    if re.search(r"^-\s*\[\s*[x ]\s*\]\s*\d+\.", b, re.MULTILINE):
        return "Decyzje"
    # Dziennik — linie z timestamp | treść (PRZED checklist, bo może zawierać |)
    if re.search(r"\d{4}-\d{2}-\d{2}[^|]*\|[^|]+$", b, re.MULTILINE) and not re.search(r"^-\s*\[", b, re.MULTILINE):
        return "Dziennik sesji"
    # Kluczowe pliki — tabela Plik | Rola
    if re.search(r"Plik\s*\|", b) or re.search(r"^-\s*`[^`]+`\s*\|", b, re.MULTILINE):
        return "Kluczowe pliki"
    # Komponenty — tabela Moduł | Plik | ...
    if re.search(r"Moduł\s*\|.*Plik", b):
        return "Komponenty"
    # Zależności — tabela Lib | Cel | Wersja
    if re.search(r"Lib.*Cel.*Wersja", b):
        return "Zależności zewnętrzne"
    # Definicja projektu — name + client
    if re.search(r"^-\s*name\s*:", b, re.MULTILINE) and re.search(r"^-\s*client\s*:", b, re.MULTILINE):
        return "Definicja projektu"
    # Listy zadań (ogólne)
    open_items = len(re.findall(r"^- \[ \]", b, re.MULTILINE))
    done_items = len(re.findall(r"^- \[x\]", b, re.MULTILINE | re.IGNORECASE))
    if open_items + done_items > 0:
        return "Następne kroki" if open_items >= done_items else "Ukończone"
    # Dziennik — linie z timestamp | treść
    if re.search(r"\d{4}-\d{2}-\d{2}.*\|", b):
        return "Dziennik sesji"
    # Fallback do mapy nazw
    return _SECTION_NAME_LABELS.get(name, name.replace("_", " ").title())


def _collect_known_projects() -> list[tuple[str, str]]:
    aliases = load_aliases()
    seen: dict[str, str] = {}
    for entry in load_history(user_history_path()):
        raw = entry.project
        if not raw:
            continue
        resolved, _ = resolve_path(raw)
        if not resolved or not Path(resolved).exists():
            continue
        if resolved not in seen:
            display = aliases.get(resolved) or aliases.get(raw) or Path(resolved).name
            seen[resolved] = display
    return [(name, path) for path, name in seen.items()]


# ---------------------------------------------------------------------------
# DiffView — widok diff z kolorami
# ---------------------------------------------------------------------------

class DiffView(QWidget):
    """Prawa kolumna: diff bieżącej treści vs punktu odniesienia (zielone/czerwone)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        hdr = QLabel("Diff (vs snapshot)")
        hdr.setStyleSheet("color:#5c6370;font-size:10px;padding:2px 4px;")
        layout.addWidget(hdr)

        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setFont(QFont("Consolas", 9))
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._view.setStyleSheet(
            "QPlainTextEdit{background:#1e2127;color:#5c6370;border:1px solid #3e4451;}"
        )
        layout.addWidget(self._view)

        self._baseline: str = ""

    def set_baseline(self, text: str) -> None:
        self._baseline = text

    def update(self, current: str) -> None:  # type: ignore[override]
        """Oblicz i wyświetl diff."""
        self._view.clear()
        if not self._baseline:
            self._view.setPlainText("(brak punktu odniesienia)")
            return

        old_lines = self._baseline.splitlines()
        new_lines = current.splitlines()

        if old_lines == new_lines:
            self._view.setPlainText("(brak zmian)")
            return

        cursor = self._view.textCursor()

        fmt_add = QTextCharFormat()
        fmt_add.setBackground(QColor("#1c3520"))
        fmt_add.setForeground(QColor("#98c379"))

        fmt_del = QTextCharFormat()
        fmt_del.setBackground(QColor("#3a1515"))
        fmt_del.setForeground(QColor("#e06c75"))

        fmt_ctx = QTextCharFormat()
        fmt_ctx.setBackground(QColor("#1e2127"))
        fmt_ctx.setForeground(QColor("#3e4451"))

        for line in difflib.ndiff(old_lines, new_lines):
            if line.startswith("+ "):
                cursor.setCharFormat(fmt_add)
                cursor.insertText(line[2:] + "\n")
            elif line.startswith("- "):
                cursor.setCharFormat(fmt_del)
                cursor.insertText(line[2:] + "\n")
            elif line.startswith("  "):
                cursor.setCharFormat(fmt_ctx)
                cursor.insertText(line[2:] + "\n")

        self._view.moveCursor(QTextCursor.MoveOperation.Start)


# ---------------------------------------------------------------------------
# PlanSectionsPanel — dolny panel dla PLAN.md
# ---------------------------------------------------------------------------

class PlanSectionsPanel(QWidget):
    """Dolna część PlanView — mapuje sekcje PLAN.md na czytelne pola."""

    task_saved = Signal()  # po zapisaniu zmian przez panel

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plan_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = QLabel("Sekcje PLAN.md")
        hdr.setStyleSheet("color:#e5c07b;font-size:11px;font-weight:bold;"
                          "padding:4px 6px;background:#21252b;border-bottom:1px solid #3e4451;")
        outer.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:#1a1d23;}")

        self._container = QWidget()
        self._container.setStyleSheet("background:#1a1d23;")
        self._rows_layout = QVBoxLayout(self._container)
        self._rows_layout.setContentsMargins(6, 6, 6, 6)
        self._rows_layout.setSpacing(4)
        self._rows_layout.addStretch()

        scroll.setWidget(self._container)
        outer.addWidget(scroll, 1)

        # Edytowalne pola dla Current / Meta
        self._edit_widgets: dict[str, QWidget] = {}

    def load(self, text: str, plan_path: Path | None = None) -> None:
        self._plan_path = plan_path
        self._edit_widgets.clear()

        # Wyczyść stare widgety
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not text.strip():
            lbl = QLabel("(brak treści)")
            lbl.setStyleSheet(_S["label"])
            self._rows_layout.insertWidget(0, lbl)
            return

        idx = 0
        for match in _SECTION_RE.finditer(text):
            name = match.group(1)
            body = match.group("body")
            role = _detect_section_role(name, body)
            widget = self._build_section_row(name, role, body.strip())
            self._rows_layout.insertWidget(idx, widget)
            idx += 1

    def _build_section_row(self, name: str, role: str, body: str) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background:#21252b;border:1px solid #2c313a;border-radius:3px;}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(3)

        # Nagłówek sekcji z rolą
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(6)
        role_lbl = QLabel(role)
        role_lbl.setStyleSheet("color:#e5c07b;font-size:10px;font-weight:bold;")
        hdr_row.addWidget(role_lbl)
        if name != role.lower().replace(" ", "_"):
            name_lbl = QLabel(f"[{name}]")
            name_lbl.setStyleSheet("color:#3e4451;font-size:9px;")
            hdr_row.addWidget(name_lbl)
        hdr_row.addStretch()
        layout.addLayout(hdr_row)

        # Treść zależna od roli
        if role == "Meta planu":
            layout.addWidget(self._build_meta(body))
        elif role == "Stan rundy":
            layout.addWidget(self._build_current(body, name))
        elif role in ("Następne kroki", "Ukończone"):
            layout.addWidget(self._build_checklist(body, role))
        elif role == "Dziennik sesji":
            layout.addWidget(self._build_log(body))
        elif role == "Blokery":
            layout.addWidget(self._build_blockers(body))
        else:
            layout.addWidget(self._build_generic(body))

        return frame

    def _build_meta(self, body: str) -> QWidget:
        meta = parse_dict(body)
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        status = meta.get("status", "?")
        color = STATUS_COLORS.get(status, "#abb2bf")
        row.addWidget(self._pill(f"● {status}", color))

        goal = meta.get("goal", "")
        if goal:
            gl = QLabel(goal[:90] + ("…" if len(goal) > 90 else ""))
            gl.setStyleSheet("color:#abb2bf;font-size:10px;")
            row.addWidget(gl, 1)

        row.addWidget(self._tag(f"Sesja {meta.get('session', '?')}"))
        row.addWidget(self._tag(meta.get("updated", "")))
        return w

    def _build_current(self, body: str, section_name: str) -> QWidget:
        current = parse_dict(body)
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        task = current.get("task", "").strip()
        file_ = current.get("file", "").strip()
        started = current.get("started", "").strip()

        # Edytowalny QLineEdit dla task
        task_row = QHBoxLayout()
        task_row.setSpacing(4)
        task_icon = QLabel("→")
        task_icon.setStyleSheet("color:#e5c07b;font-size:12px;")
        task_row.addWidget(task_icon)
        self._task_edit = QLineEdit(task)
        self._task_edit.setPlaceholderText("(brak aktywnego zadania)")
        self._task_edit.setStyleSheet(
            "QLineEdit{background:#1e2127;color:#e5c07b;border:1px solid #3e4451;"
            "border-radius:2px;padding:2px 6px;font-size:11px;}"
            "QLineEdit:focus{border-color:#61afef;}"
        )
        task_row.addWidget(self._task_edit, 1)
        self._edit_widgets[f"{section_name}_task"] = self._task_edit
        layout.addLayout(task_row)

        if file_ or started:
            meta_row = QHBoxLayout()
            meta_row.setSpacing(8)
            if file_:
                meta_row.addWidget(self._tag(f"📄 {file_}", "#61afef"))
            if started:
                meta_row.addWidget(self._tag(started))
            meta_row.addStretch()
            layout.addLayout(meta_row)

        # Przycisk zapisz zmianę
        save_row = QHBoxLayout()
        save_row.addStretch()
        btn = QPushButton("Zapisz zadanie")
        btn.setStyleSheet(_S["save"])
        btn.setFixedHeight(22)
        btn.clicked.connect(lambda: self._save_current_task(section_name))
        save_row.addWidget(btn)
        layout.addLayout(save_row)

        return w

    def _save_current_task(self, section_name: str) -> None:
        if self._plan_path is None:
            return
        key = f"{section_name}_task"
        edit = self._edit_widgets.get(key)
        if edit is None:
            return
        new_task = edit.text().strip()
        try:
            text = self._plan_path.read_text(encoding="utf-8")
            current = parse_dict(read_section(text, section_name) or "")
            current["task"] = new_task
            current["started"] = current.get("started") or datetime.now().strftime("%Y-%m-%d %H:%M")
            text = write_section(text, section_name, build_dict(current))
            self._plan_path.write_text(text, encoding="utf-8")
            self.task_saved.emit()
        except Exception as exc:
            QMessageBox.critical(None, "Błąd zapisu", str(exc))

    def _build_checklist(self, body: str, role: str) -> QWidget:
        items = parse_list(body)
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        if not items:
            lbl = QLabel("(puste)")
            lbl.setStyleSheet("color:#5c6370;font-size:10px;")
            layout.addWidget(lbl)
            return w

        for item in items[:10]:
            mark = "✓" if item["done"] else "○"
            color = "#98c379" if item["done"] else "#abb2bf"
            text = item["text"][:90]
            lbl = QLabel(f"{mark}  {text}")
            lbl.setStyleSheet(f"color:{color};font-size:10px;")
            layout.addWidget(lbl)

        if len(items) > 10:
            more = QLabel(f"… i {len(items) - 10} więcej")
            more.setStyleSheet("color:#5c6370;font-size:10px;")
            layout.addWidget(more)

        return w

    def _build_log(self, body: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        lines = [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("<!--")]
        for line in reversed(lines[-4:]):
            lbl = QLabel(line[:110])
            lbl.setStyleSheet("color:#5c6370;font-size:9px;")
            layout.addWidget(lbl)
        if not lines:
            layout.addWidget(self._tag("(brak wpisów)"))
        return w

    def _build_blockers(self, body: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        if body.strip():
            lbl = QLabel(body.strip()[:200])
            lbl.setStyleSheet("color:#e06c75;font-size:10px;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
        else:
            layout.addWidget(self._tag("(brak blokerów)"))
        return w

    def _build_generic(self, body: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        preview = body.strip()[:200]
        lbl = QLabel(preview + ("…" if len(body.strip()) > 200 else "") or "(pusta sekcja)")
        lbl.setStyleSheet("color:#5c6370;font-size:10px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        return w

    @staticmethod
    def _pill(text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{color};font-size:11px;font-weight:bold;"
            f"border:1px solid {color};border-radius:3px;padding:1px 6px;"
        )
        return lbl

    @staticmethod
    def _tag(text: str, color: str = "#5c6370") -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{color};font-size:10px;")
        return lbl


# ---------------------------------------------------------------------------
# PlanView — główny widok dla PLAN.md
# ---------------------------------------------------------------------------

class PlanView(QWidget):
    """Widok PLAN.md: lewy (edytor) + prawy (diff) + dolny (sekcje PCC)."""

    saved = Signal()
    dirty_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path: Path | None = None
        self._snapshot: str = ""
        self._loading = False
        self._dirty = False
        self._diff_timer = QTimer(self)
        self._diff_timer.setSingleShot(True)
        self._diff_timer.setInterval(400)
        self._diff_timer.timeout.connect(self._refresh_diff)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background:#21252b;border-bottom:1px solid #3e4451;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(6, 4, 6, 4)
        tb_layout.setSpacing(6)

        self._file_lbl = QLabel("PLAN.md")
        self._file_lbl.setStyleSheet("color:#e5c07b;font-size:11px;font-weight:bold;")
        tb_layout.addWidget(self._file_lbl)

        self._dirty_lbl = QLabel("● niezapisane")
        self._dirty_lbl.setStyleSheet("color:#e5c07b;font-size:10px;")
        self._dirty_lbl.setVisible(False)
        tb_layout.addWidget(self._dirty_lbl)

        tb_layout.addStretch()

        self._snapshot_lbl = QLabel()
        self._snapshot_lbl.setStyleSheet("color:#5c6370;font-size:10px;")
        tb_layout.addWidget(self._snapshot_lbl)

        btn_reload = QPushButton("Odśwież snapshot")
        btn_reload.setStyleSheet(_S["btn"])
        btn_reload.setFixedHeight(22)
        btn_reload.setToolTip("Ustaw aktualną treść jako punkt odniesienia dla diff")
        btn_reload.clicked.connect(self._reset_snapshot)
        tb_layout.addWidget(btn_reload)

        btn_discard = QPushButton("Porzuć")
        btn_discard.setStyleSheet(_S["discard"])
        btn_discard.setFixedHeight(22)
        btn_discard.clicked.connect(self._discard)
        tb_layout.addWidget(btn_discard)

        btn_save = QPushButton("Zapisz")
        btn_save.setStyleSheet(_S["save"])
        btn_save.setFixedHeight(22)
        btn_save.clicked.connect(self._save)
        tb_layout.addWidget(btn_save)

        root.addWidget(toolbar)

        # Główny splitter pionowy: (edytor+diff) | sekcje
        v_split = QSplitter(Qt.Orientation.Vertical)

        # Górna część: splitter poziomy edytor | diff
        h_split = QSplitter(Qt.Orientation.Horizontal)

        # Lewy — edytor raw
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(2)
        raw_hdr = QLabel("Treść pliku (edytowalny)")
        raw_hdr.setStyleSheet("color:#5c6370;font-size:10px;padding:2px 4px;")
        left_lay.addWidget(raw_hdr)
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setStyleSheet(_S["editor"])
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.textChanged.connect(self._on_text_changed)
        left_lay.addWidget(self._editor)
        h_split.addWidget(left_w)

        # Prawy — diff
        self._diff = DiffView()
        h_split.addWidget(self._diff)
        h_split.setSizes([500, 500])
        h_split.setCollapsible(0, False)
        h_split.setCollapsible(1, False)

        v_split.addWidget(h_split)

        # Dolna część — sekcje PLAN
        self._sections = PlanSectionsPanel()
        self._sections.setMinimumHeight(160)
        self._sections.task_saved.connect(self._on_task_saved)
        v_split.addWidget(self._sections)
        v_split.setSizes([420, 200])
        v_split.setCollapsible(0, False)
        v_split.setCollapsible(1, False)

        root.addWidget(v_split, 1)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load(self, path: Path) -> None:
        self._file_path = path
        self._file_lbl.setText(path.name)
        text = path.read_text(encoding="utf-8")
        self._loading = True
        self._editor.setPlainText(text)
        self._loading = False
        self._snapshot = text
        self._diff.set_baseline(text)
        self._diff.update(text)
        self._sections.load(text, path)
        self._set_dirty(False)
        self._update_snapshot_label()

    def reload_from_disk(self) -> None:
        if self._file_path and self._file_path.exists():
            self.load(self._file_path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        self._set_dirty(True)
        self._diff_timer.start()

    def _refresh_diff(self) -> None:
        self._diff.update(self._editor.toPlainText())

    def _reset_snapshot(self) -> None:
        text = self._editor.toPlainText()
        self._snapshot = text
        self._diff.set_baseline(text)
        self._diff.update(text)
        self._update_snapshot_label()

    def _update_snapshot_label(self) -> None:
        self._snapshot_lbl.setText(f"Snapshot: {datetime.now().strftime('%H:%M:%S')}")

    def _save(self) -> None:
        if self._file_path is None:
            return
        text = self._editor.toPlainText()
        self._file_path.write_text(text, encoding="utf-8")
        self._set_dirty(False)
        self._sections.load(text, self._file_path)
        self.saved.emit()

    def _discard(self) -> None:
        if self._file_path and self._file_path.exists():
            self.load(self._file_path)

    def _on_task_saved(self) -> None:
        if self._file_path and self._file_path.exists():
            text = self._file_path.read_text(encoding="utf-8")
            self._loading = True
            self._editor.setPlainText(text)
            self._loading = False
            self._set_dirty(False)
            self._refresh_diff()

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._dirty_lbl.setVisible(dirty)
        self.dirty_changed.emit(dirty)


# ---------------------------------------------------------------------------
# PccSectionsPanel — dolny panel dla plików PCC (CLAUDE/ARCH/CONV)
# ---------------------------------------------------------------------------

class PccSectionsPanel(QWidget):
    """Dolna część PccView — semantyczne mapowanie sekcji PCC."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = QLabel("Sekcje PCC")
        hdr.setStyleSheet("color:#e5c07b;font-size:11px;font-weight:bold;"
                          "padding:4px 6px;background:#21252b;border-bottom:1px solid #3e4451;")
        outer.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:#1a1d23;}")

        self._container = QWidget()
        self._container.setStyleSheet("background:#1a1d23;")
        self._grid = QVBoxLayout(self._container)
        self._grid.setContentsMargins(6, 6, 6, 6)
        self._grid.setSpacing(3)
        self._grid.addStretch()

        scroll.setWidget(self._container)
        outer.addWidget(scroll, 1)

    def load(self, text: str) -> None:
        while self._grid.count() > 1:
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sections = list(_SECTION_RE.finditer(text))
        if not sections:
            lbl = QLabel("(brak sekcji PCC w pliku)")
            lbl.setStyleSheet("color:#5c6370;font-size:10px;padding:4px;")
            self._grid.insertWidget(0, lbl)
            return

        for idx, match in enumerate(sections):
            name = match.group(1)
            body = match.group("body").strip()
            role = _detect_section_role(name, body)
            row = self._build_row(name, role, body)
            self._grid.insertWidget(idx, row)

    def _build_row(self, name: str, role: str, body: str) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background:#21252b;border:1px solid #2c313a;"
            "border-radius:3px;margin:0px;}"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        # Label roli (semantyczny)
        role_lbl = QLabel(role)
        role_lbl.setFixedWidth(160)
        role_lbl.setStyleSheet("color:#e5c07b;font-size:10px;font-weight:bold;")
        lay.addWidget(role_lbl)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#3e4451;")
        lay.addWidget(sep)

        # Podgląd treści
        preview = body.replace("\n", "  ·  ")[:140]
        preview_lbl = QLabel(preview or "(pusta sekcja)")
        preview_lbl.setStyleSheet("color:#5c6370;font-size:10px;")
        preview_lbl.setWordWrap(False)
        lay.addWidget(preview_lbl, 1)

        # Marker nazwy sekcji po prawej
        marker_lbl = QLabel(f"[{name}]")
        marker_lbl.setStyleSheet("color:#2c313a;font-size:9px;")
        lay.addWidget(marker_lbl)

        return frame


# ---------------------------------------------------------------------------
# PccView — widok dla CLAUDE.md / ARCHITECTURE.md / CONVENTIONS.md
# ---------------------------------------------------------------------------

class PccView(QWidget):
    """Widok pliku PCC: góra (edytor raw) + dół (semantyczne sekcje)."""

    saved = Signal()
    dirty_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path: Path | None = None
        self._loading = False
        self._dirty = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background:#21252b;border-bottom:1px solid #3e4451;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(6, 4, 6, 4)
        tb_layout.setSpacing(6)

        self._file_lbl = QLabel()
        self._file_lbl.setStyleSheet("color:#e5c07b;font-size:11px;font-weight:bold;")
        tb_layout.addWidget(self._file_lbl)

        self._dirty_lbl = QLabel("● niezapisane")
        self._dirty_lbl.setStyleSheet("color:#e5c07b;font-size:10px;")
        self._dirty_lbl.setVisible(False)
        tb_layout.addWidget(self._dirty_lbl)

        tb_layout.addStretch()

        btn_discard = QPushButton("Porzuć")
        btn_discard.setStyleSheet(_S["discard"])
        btn_discard.setFixedHeight(22)
        btn_discard.clicked.connect(self._discard)
        tb_layout.addWidget(btn_discard)

        btn_save = QPushButton("Zapisz")
        btn_save.setStyleSheet(_S["save"])
        btn_save.setFixedHeight(22)
        btn_save.clicked.connect(self._save)
        tb_layout.addWidget(btn_save)

        root.addWidget(toolbar)

        # Splitter pionowy: edytor | sekcje PCC
        v_split = QSplitter(Qt.Orientation.Vertical)

        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setStyleSheet(_S["editor"])
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.textChanged.connect(self._on_text_changed)
        v_split.addWidget(self._editor)

        self._sections = PccSectionsPanel()
        self._sections.setMinimumHeight(120)
        v_split.addWidget(self._sections)
        v_split.setSizes([500, 200])
        v_split.setCollapsible(0, False)
        v_split.setCollapsible(1, False)

        root.addWidget(v_split, 1)

    def load(self, path: Path) -> None:
        self._file_path = path
        self._file_lbl.setText(path.name)
        text = path.read_text(encoding="utf-8")
        self._loading = True
        self._editor.setPlainText(text)
        self._loading = False
        self._sections.load(text)
        self._set_dirty(False)

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        self._set_dirty(True)
        # Odśwież sekcje z opóźnieniem
        QTimer.singleShot(600, lambda: self._sections.load(self._editor.toPlainText()))

    def _save(self) -> None:
        if self._file_path is None:
            return
        text = self._editor.toPlainText()
        self._file_path.write_text(text, encoding="utf-8")
        self._sections.load(text)
        self._set_dirty(False)
        self.saved.emit()

    def _discard(self) -> None:
        if self._file_path and self._file_path.exists():
            self.load(self._file_path)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._dirty_lbl.setVisible(dirty)
        self.dirty_changed.emit(dirty)


# ---------------------------------------------------------------------------
# SSS helpers
# ---------------------------------------------------------------------------

def _find_cc_sss() -> str | None:
    """Zwraca ścieżkę do claude/cc CLI."""
    home = Path.home()
    if sys.platform == "win32":
        npm = home / "AppData" / "Roaming" / "npm"
        exe = npm / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
        for c in [npm / "claude.CMD", npm / "claude.cmd", npm / "cc.cmd", npm / "cc"]:
            if c.exists():
                return str(c)
    return shutil.which("cc") or shutil.which("claude")


def _sss_scripts_dir() -> Path:
    """Ścieżka do katalogu skryptów SSS."""
    return Path.home() / ".claude" / "skills" / "sss" / "scripts"


# ---------------------------------------------------------------------------
# SssRundaWstepnaPanel — Runda Wstępna SSS osadzona w Projektancie
# ---------------------------------------------------------------------------

class SssRundaWstepnaPanel(QWidget):
    """Panel Rundy Wstępnej SSS — zbiera opis projektu, generuje intake.json,
    uruchamia init_project.py i zwraca gotowy katalog projektu."""

    project_initialized = Signal(Path)  # emitowany po akceptacji projektu

    _PYTANIA_PROMPT = (
        "Jesteś asystentem planowania projektów programistycznych.\n"
        "User opisał swój projekt. Zadaj DOKŁADNIE 3 pytania, które rozwiążą "
        "największe niejasności potrzebne do zainicjowania projektu.\n"
        "Jedno pytanie = jeden konkret, bez alternatyw.\n"
        "Format: wyłącznie lista 3 pytań w stylu markdown:\n"
        "1. Pytanie pierwsze\n2. Pytanie drugie\n3. Pytanie trzecie\n\n"
        "Opis projektu od usera:\n{opis}"
    )

    _INTAKE_PROMPT = (
        "Jesteś asystentem inicjalizacji projektów. Na podstawie opisu projektu "
        "i odpowiedzi na pytania wygeneruj JSON w ściśle określonym formacie.\n\n"
        "Odpowiedz WYŁĄCZNIE poprawnym JSON — bez komentarzy, bez bloków ```.\n\n"
        'Format (wszystkie pola wymagane, wartości po polsku, puste = ""):\n'
        "{\n"
        '  "project": {"title": "...", "type": "...", "client": "...", '
        '"stack": "...", "one_liner": "..."},\n'
        '  "claude": {"off_limits": "...", "specifics": "..."},\n'
        '  "architecture": {"overview": "...", "components": "...", '
        '"data_flow": "...", "decisions": "...", "constraints": "..."},\n'
        '  "conventions": {"naming": "...", "file_layout": "...", "anti_patterns": "..."},\n'
        '  "plan": {"goal": "...", "current": "...", "current_file": "...", "next": "..."}\n'
        "}\n\n"
        "Opis projektu:\n{opis}\n\n"
        "Odpowiedzi na pytania:\n{odpowiedzi}"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._process: QProcess | None = None
        self._mode: str = ""  # "pytania" | "intake" | "init"
        self._output_buf: str = ""
        self._intake_json: dict = {}
        self._setup_ui()

    def set_project_path(self, path: Path | None) -> None:
        self._project_path = path
        self._lbl_target.setText(str(path) if path else "(brak — wskaż projekt)")
        self._btn_init.setEnabled(bool(path))

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Nagłówek
        hdr = QHBoxLayout()
        title = QLabel("★ Runda Wstępna SSS")
        title.setStyleSheet("color:#e5c07b;font-size:13px;font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._badge = QLabel("")
        self._badge.setStyleSheet(
            "background:#1a3a1a;color:#98c379;border-radius:3px;"
            "padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        self._badge.setVisible(False)
        hdr.addWidget(self._badge)
        root.addLayout(hdr)

        desc = QLabel(
            "Opisz projekt — AI zada 3 pytania, po odpowiedziach wygeneruje "
            "strukturę DPS (CLAUDE.md, ARCHITECTURE.md, PLAN.md, CONVENTIONS.md)."
        )
        desc.setStyleSheet("color:#5c6370;font-size:10px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Katalog docelowy
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Katalog projektu:", styleSheet="color:#9cdcfe;font-size:10px;"))
        self._lbl_target = QLabel("(brak)")
        self._lbl_target.setStyleSheet("color:#5c6370;font-size:10px;font-family:Consolas;")
        self._lbl_target.setWordWrap(True)
        target_row.addWidget(self._lbl_target, 1)
        btn_browse = QPushButton("Zmień…")
        btn_browse.setStyleSheet(_S["btn"])
        btn_browse.setFixedHeight(22)
        btn_browse.clicked.connect(self._browse_target)
        target_row.addWidget(btn_browse)
        root.addLayout(target_row)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color:#3e4451;")
        root.addWidget(sep1)

        # Splitter: góra (wejście) / dół (AI)
        v_split = QSplitter(Qt.Orientation.Vertical)

        # ── Góra: opis + pytania + odpowiedzi ───────────────────────────
        top_w = QWidget()
        top_lay = QVBoxLayout(top_w)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(6)

        top_lay.addWidget(QLabel("Opis projektu:", styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;"))
        self._opis_edit = QPlainTextEdit()
        self._opis_edit.setFont(QFont("Consolas", 9))
        self._opis_edit.setFixedHeight(90)
        self._opis_edit.setPlaceholderText(
            "Opisz: co budujesz, dla kogo, stack, główny cel, constraints…"
        )
        self._opis_edit.setStyleSheet(_S["editor"])
        top_lay.addWidget(self._opis_edit)

        btn_row1 = QHBoxLayout()
        self._btn_pytania = QPushButton("▶ Generuj 3 pytania")
        self._btn_pytania.setStyleSheet(_S["new"])
        self._btn_pytania.clicked.connect(self._on_pytania)
        btn_row1.addWidget(self._btn_pytania)
        self._btn_stop = QPushButton("■ Stop")
        self._btn_stop.setStyleSheet(_S["discard"])
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)
        btn_row1.addWidget(self._btn_stop)
        btn_row1.addStretch()
        self._lbl_status = QLabel("", styleSheet="color:#5c6370;font-size:10px;")
        btn_row1.addWidget(self._lbl_status)
        top_lay.addLayout(btn_row1)

        top_lay.addWidget(QLabel("Pytania AI:", styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;"))
        self._pytania_view = QPlainTextEdit()
        self._pytania_view.setFont(QFont("Consolas", 9))
        self._pytania_view.setReadOnly(True)
        self._pytania_view.setFixedHeight(80)
        self._pytania_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#61afef;"
            "border:1px solid #1a3a4a;border-radius:3px;padding:4px;}"
        )
        self._pytania_view.setPlaceholderText("Tutaj pojawią się 3 pytania AI…")
        top_lay.addWidget(self._pytania_view)

        top_lay.addWidget(QLabel("Twoje odpowiedzi:", styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;"))
        self._odpowiedzi_edit = QPlainTextEdit()
        self._odpowiedzi_edit.setFont(QFont("Consolas", 9))
        self._odpowiedzi_edit.setFixedHeight(80)
        self._odpowiedzi_edit.setPlaceholderText("1. …\n2. …\n3. …")
        self._odpowiedzi_edit.setStyleSheet(_S["editor"])
        top_lay.addWidget(self._odpowiedzi_edit)

        btn_row2 = QHBoxLayout()
        self._btn_intake = QPushButton("▶ Generuj intake.json")
        self._btn_intake.setStyleSheet(_S["btn"])
        self._btn_intake.setEnabled(False)
        self._btn_intake.clicked.connect(self._on_intake)
        btn_row2.addWidget(self._btn_intake)
        btn_row2.addStretch()
        top_lay.addLayout(btn_row2)

        v_split.addWidget(top_w)

        # ── Dół: podgląd intake + inicjalizacja ─────────────────────────
        bot_w = QWidget()
        bot_lay = QVBoxLayout(bot_w)
        bot_lay.setContentsMargins(0, 0, 0, 0)
        bot_lay.setSpacing(6)

        bot_lay.addWidget(QLabel("Podgląd intake.json:", styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;"))
        self._intake_view = QPlainTextEdit()
        self._intake_view.setFont(QFont("Consolas", 9))
        self._intake_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#98c379;"
            "border:1px solid #1a3a4a;border-radius:3px;padding:4px;}"
        )
        self._intake_view.setPlaceholderText("Tu pojawi się wygenerowany intake.json…")
        bot_lay.addWidget(self._intake_view, 1)

        bot_lay.addWidget(QLabel("Wynik init_project.py:", styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;"))
        self._init_view = QPlainTextEdit()
        self._init_view.setFont(QFont("Consolas", 9))
        self._init_view.setReadOnly(True)
        self._init_view.setFixedHeight(60)
        self._init_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#e5c07b;"
            "border:1px solid #3a3a1a;border-radius:3px;padding:4px;}"
        )
        bot_lay.addWidget(self._init_view)

        btn_row3 = QHBoxLayout()
        self._btn_init = QPushButton("✦ Inicjuj projekt (init_project.py)")
        self._btn_init.setStyleSheet(_S["save"])
        self._btn_init.setEnabled(False)
        self._btn_init.clicked.connect(self._on_init)
        btn_row3.addWidget(self._btn_init)

        self._btn_accept = QPushButton("✓ Akceptuj i otwórz projekt")
        self._btn_accept.setStyleSheet(
            "QPushButton{background:#1a2a3a;color:#61afef;"
            "border:1px solid #2a4a6a;border-radius:3px;padding:4px 14px;font-weight:bold}"
            "QPushButton:hover{background:#2a4a6a}"
            "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
        )
        self._btn_accept.setEnabled(False)
        self._btn_accept.clicked.connect(self._on_accept)
        btn_row3.addWidget(self._btn_accept)
        btn_row3.addStretch()
        bot_lay.addLayout(btn_row3)

        v_split.addWidget(bot_w)
        v_split.setSizes([320, 280])
        root.addWidget(v_split, 1)

    # ── Akcje ────────────────────────────────────────────────────────────

    def _browse_target(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Wskaż katalog projektu")
        if path:
            self.set_project_path(Path(path))

    def _on_pytania(self) -> None:
        opis = self._opis_edit.toPlainText().strip()
        if not opis:
            QMessageBox.warning(self, "SSS", "Opisz projekt przed generowaniem pytań.")
            return
        cc = _find_cc_sss()
        if not cc:
            QMessageBox.warning(self, "SSS", "Nie znaleziono claude/cc w PATH.")
            return
        prompt = self._PYTANIA_PROMPT.format(opis=opis)
        self._start_ai(cc, prompt, mode="pytania")

    def _on_intake(self) -> None:
        opis = self._opis_edit.toPlainText().strip()
        odpowiedzi = self._odpowiedzi_edit.toPlainText().strip()
        cc = _find_cc_sss()
        if not cc:
            QMessageBox.warning(self, "SSS", "Nie znaleziono claude/cc w PATH.")
            return
        prompt = self._INTAKE_PROMPT.format(opis=opis, odpowiedzi=odpowiedzi or "(brak)")
        self._start_ai(cc, prompt, mode="intake")

    def _on_init(self) -> None:
        if not self._project_path:
            QMessageBox.warning(self, "SSS", "Wskaż katalog projektu.")
            return
        intake_text = self._intake_view.toPlainText().strip()
        if not intake_text:
            QMessageBox.warning(self, "SSS", "Brak intake.json — wygeneruj go najpierw.")
            return
        try:
            self._intake_json = json.loads(intake_text)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "SSS", f"Niepoprawny JSON:\n{e}")
            return

        intake_path = self._project_path / "intake.json"
        try:
            intake_path.write_text(json.dumps(self._intake_json, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "SSS", f"Nie można zapisać intake.json:\n{e}")
            return

        scripts_dir = _sss_scripts_dir()
        init_script = scripts_dir / "init_project.py"
        if not init_script.exists():
            QMessageBox.critical(self, "SSS", f"Brak skryptu:\n{init_script}")
            return

        python = shutil.which("python") or shutil.which("python3") or sys.executable
        self._init_view.clear()
        self._lbl_status.setText("Inicjalizuję projekt…")
        self._btn_init.setEnabled(False)
        self._mode = "init"

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.setProgram(python)
        self._process.setArguments([
            str(init_script),
            "--intake", str(intake_path),
            "--target", str(self._project_path),
        ])
        self._process.start()
        if not self._process.waitForStarted(3000):
            self._lbl_status.setText("Błąd startu skryptu")
            self._btn_init.setEnabled(True)

    def _on_accept(self) -> None:
        if self._project_path:
            self.project_initialized.emit(self._project_path)
            self._badge.setText("✓ Projekt gotowy")
            self._badge.setVisible(True)

    def _on_stop(self) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
        self._lbl_status.setText("Przerwano")
        self._btn_pytania.setEnabled(True)
        self._btn_stop.setEnabled(False)

    # ── AI process helpers ───────────────────────────────────────────────

    def _start_ai(self, cc: str, prompt: str, mode: str) -> None:
        self._mode = mode
        self._output_buf = ""
        if mode == "pytania":
            self._pytania_view.clear()
        else:
            self._intake_view.clear()
        self._btn_pytania.setEnabled(False)
        self._btn_intake.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._lbl_status.setText("AI pracuje…")

        self._process = QProcess(self)
        self._process.setProgram(cc)
        self._process.setArguments(["--print", "--output-format", "stream-json"])
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start()
        if not self._process.waitForStarted(3000):
            self._lbl_status.setText("Błąd startu AI")
            self._btn_pytania.setEnabled(True)
            self._btn_stop.setEnabled(False)
            return
        self._process.write(prompt.encode("utf-8"))
        self._process.closeWriteChannel()

    def _on_stdout(self) -> None:
        if not self._process:
            return
        raw = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if self._mode == "init":
                self._init_view.moveCursor(QTextCursor.MoveOperation.End)
                self._init_view.insertPlainText(line + "\n")
                continue
            try:
                obj = json.loads(line)
                chunk = ""
                if obj.get("type") == "content_block_delta":
                    chunk = obj.get("delta", {}).get("text", "")
                elif obj.get("type") == "text":
                    chunk = obj.get("text", "")
                elif obj.get("type") == "result":
                    chunk = obj.get("result", "")
                if chunk:
                    self._output_buf += chunk
                    target = self._pytania_view if self._mode == "pytania" else self._intake_view
                    target.moveCursor(QTextCursor.MoveOperation.End)
                    target.insertPlainText(chunk)
            except (json.JSONDecodeError, KeyError):
                self._output_buf += line + "\n"
                target = self._pytania_view if self._mode == "pytania" else self._intake_view
                target.moveCursor(QTextCursor.MoveOperation.End)
                target.insertPlainText(line + "\n")

    def _on_stderr(self) -> None:
        if not self._process:
            return
        raw = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if raw.strip() and self._mode != "init":
            target = self._pytania_view if self._mode == "pytania" else self._intake_view
            target.moveCursor(QTextCursor.MoveOperation.End)
            target.insertPlainText(f"[STDERR] {raw}")

    def _on_finished(self, exit_code: int, _status) -> None:
        self._btn_pytania.setEnabled(True)
        self._btn_stop.setEnabled(False)
        if self._mode == "pytania":
            has = bool(self._output_buf.strip())
            self._btn_intake.setEnabled(has)
            self._lbl_status.setText("Gotowe — wpisz odpowiedzi" if has else f"Błąd (kod {exit_code})")
        elif self._mode == "intake":
            raw = self._output_buf.strip()
            # Wyciągnij JSON jeśli owinięty w ```json
            m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
            if m:
                raw = m.group(1).strip()
                self._intake_view.setPlainText(raw)
            self._btn_init.setEnabled(bool(raw) and bool(self._project_path))
            self._lbl_status.setText("Sprawdź intake.json i kliknij Inicjuj" if raw else f"Błąd (kod {exit_code})")
        elif self._mode == "init":
            self._btn_init.setEnabled(True)
            if exit_code == 0:
                self._btn_accept.setEnabled(True)
                self._lbl_status.setText("Projekt zainicjowany — akceptuj lub popraw")
            else:
                self._lbl_status.setText(f"Błąd inicjalizacji (kod {exit_code})")


# ---------------------------------------------------------------------------
# NewProjectDialog (bez zmian)
# ---------------------------------------------------------------------------

class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nowy projekt — Projektant CC")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._result_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(8)

        _le_style = ("QLineEdit{background:#21252b;color:#e5c07b;border:1px solid #3e4451;"
                     "border-radius:3px;padding:4px 8px;font-size:12px;}")
        _le_style2 = _le_style.replace("#e5c07b", "#abb2bf")

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("np. moj-projekt")
        self._name_edit.setStyleSheet(_le_style)
        form.addRow("Nazwa projektu:", self._name_edit)

        self._type_edit = QLineEdit()
        self._type_edit.setPlaceholderText("np. moduł Claude Manager, web app, API...")
        self._type_edit.setStyleSheet(_le_style2)
        form.addRow("Typ projektu:", self._type_edit)

        layout.addLayout(form)

        dir_layout = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setPlaceholderText("Katalog nadrzędny...")
        self._dir_edit.setStyleSheet(_le_style2)
        dir_layout.addWidget(self._dir_edit, 1)
        btn_dir = QPushButton("Wybierz...")
        btn_dir.setStyleSheet(_S["btn"])
        btn_dir.clicked.connect(self._browse)
        dir_layout.addWidget(btn_dir)
        layout.addLayout(dir_layout)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet("color:#5c6370;font-size:11px;padding:2px 0;")
        layout.addWidget(self._preview_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#3e4451;")
        layout.addWidget(sep)

        info = QLabel("Zostaną utworzone pliki (PCC): " + ", ".join(PROJECT_FILES))
        info.setStyleSheet("color:#5c6370;font-size:10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Utwórz projekt")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(_S["new"])
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(_S["btn"])
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._name_edit.textChanged.connect(self._update_preview)
        self._dir_edit.textChanged.connect(self._update_preview)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Wybierz katalog nadrzędny")
        if path:
            self._dir_edit.setText(path)

    def _update_preview(self) -> None:
        name = self._name_edit.text().strip()
        parent = self._dir_edit.text().strip()
        if name and parent:
            self._preview_label.setText(f"Zostanie utworzony: {parent}/{name}/")
        elif name:
            self._preview_label.setText("Wskaż katalog nadrzędny")
        else:
            self._preview_label.setText("")

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        parent = self._dir_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Błąd", "Podaj nazwę projektu.")
            return
        if not parent:
            QMessageBox.warning(self, "Błąd", "Wskaż katalog nadrzędny.")
            return
        safe_name = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in name)
        dest = Path(parent) / safe_name
        if dest.exists():
            QMessageBox.warning(self, "Błąd", f"Folder już istnieje:\n{dest}")
            return
        self._result_path = dest
        self._project_name = name
        self._project_type = self._type_edit.text().strip()
        self.accept()

    @property
    def result_path(self) -> Path | None:
        return self._result_path

    @property
    def project_name(self) -> str:
        return getattr(self, "_project_name", "")

    @property
    def project_type(self) -> str:
        return getattr(self, "_project_type", "")


# ---------------------------------------------------------------------------
# ProjectantPanel — główny panel Projektanta
# ---------------------------------------------------------------------------

class ProjectantPanel(QWidget):
    """Tab panel Projektant CC — pliki PLAN.md i PCC z widokami sekcji i diff."""

    project_ready = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._known_projects: list[tuple[str, str]] = []
        self._current_file: Path | None = None
        self._setup_ui()
        self._load_known_projects()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- Top bar ---
        top = QHBoxLayout()
        top.setSpacing(6)

        lbl = QLabel("Projekt:")
        lbl.setStyleSheet(_S["label"])
        top.addWidget(lbl)

        self._project_combo = QComboBox()
        self._project_combo.setMinimumWidth(300)
        self._project_combo.setStyleSheet(_S["combo"])
        self._project_combo.currentIndexChanged.connect(self._on_combo_changed)
        top.addWidget(self._project_combo, 1)

        btn_browse = QPushButton("Wskaż...")
        btn_browse.setStyleSheet(_S["btn"])
        btn_browse.clicked.connect(self._browse_project)
        top.addWidget(btn_browse)

        btn_new = QPushButton("+ Nowy projekt")
        btn_new.setStyleSheet(_S["new"])
        btn_new.clicked.connect(self._new_project)
        top.addWidget(btn_new)

        btn_wizard = QPushButton("Kreator...")
        btn_wizard.setStyleSheet(_S["btn"])
        btn_wizard.clicked.connect(self._open_wizard)
        top.addWidget(btn_wizard)

        btn_ai = QPushButton("✨ AI Wizard")
        btn_ai.setStyleSheet(_S["new"])
        btn_ai.clicked.connect(self._open_ai_wizard)
        top.addWidget(btn_ai)

        btn_sss = QPushButton("★ Runda Wstępna")
        btn_sss.setStyleSheet(
            "QPushButton{background:#2a1a00;color:#e5c07b;border:1px solid #5a4000;"
            "border-radius:3px;padding:4px 10px;font-size:11px;font-weight:bold;}"
            "QPushButton:hover{background:#3a2a00;}"
            "QPushButton:checked{background:#3a2a00;border-color:#e5c07b;}"
        )
        btn_sss.setCheckable(True)
        btn_sss.clicked.connect(self._toggle_sss_panel)
        top.addWidget(btn_sss)
        self._btn_sss = btn_sss

        root.addLayout(top)

        self._path_label = QLabel()
        self._path_label.setStyleSheet("color:#5c6370;font-size:10px;padding:0 2px;")
        root.addWidget(self._path_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#3e4451;")
        root.addWidget(sep)

        # --- Splitter: lista plików (lewo) + widok (prawo) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lewa: lista plików
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)

        files_lbl = QLabel("Pliki projektowe")
        files_lbl.setStyleSheet(_S["title"])
        left_lay.addWidget(files_lbl)

        self._file_list = QListWidget()
        self._file_list.setStyleSheet(_S["list"])
        self._file_list.currentItemChanged.connect(self._on_file_selected)
        left_lay.addWidget(self._file_list, 1)

        create_lbl = QLabel("Utwórz z szablonu:")
        create_lbl.setStyleSheet(_S["label"])
        left_lay.addWidget(create_lbl)

        self._create_buttons: dict[str, QPushButton] = {}
        for fname in PROJECT_FILES:
            template = fname.replace(".md", "")
            btn = QPushButton(f"+ {fname}")
            btn.setStyleSheet(_S["create"])
            btn.clicked.connect(
                lambda checked=False, t=template, f=fname: self._create_file(t, f)
            )
            left_lay.addWidget(btn)
            self._create_buttons[fname] = btn

        btn_ext = QPushButton("Otwórz w edytorze")
        btn_ext.setStyleSheet(_S["btn"])
        btn_ext.clicked.connect(self._open_in_editor)
        left_lay.addWidget(btn_ext)
        self._btn_open_editor = btn_ext

        splitter.addWidget(left)

        # Prawa: QStackedWidget z PlanView i PccView
        self._view_stack = QStackedWidget()

        self._plan_view = PlanView()
        self._plan_view.saved.connect(lambda: self._on_view_saved("PLAN.md"))
        self._view_stack.addWidget(self._plan_view)   # index 0

        self._pcc_view = PccView()
        self._pcc_view.saved.connect(lambda: self._on_view_saved(""))
        self._view_stack.addWidget(self._pcc_view)    # index 1

        self._empty_view = QLabel("Wybierz plik z listy po lewej")
        self._empty_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_view.setStyleSheet("color:#5c6370;font-size:13px;")
        self._view_stack.addWidget(self._empty_view)  # index 2

        self._sss_panel = SssRundaWstepnaPanel()
        self._sss_panel.project_initialized.connect(self._on_sss_project_initialized)
        self._view_stack.addWidget(self._sss_panel)   # index 3

        splitter.addWidget(self._view_stack)
        splitter.setSizes([220, 980])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root.addWidget(splitter, 1)
        self._refresh_ui()

    # ------------------------------------------------------------------
    # Known projects
    # ------------------------------------------------------------------

    def _load_known_projects(self) -> None:
        self._known_projects = _collect_known_projects()
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("— wybierz projekt —", None)
        for display, path in self._known_projects:
            self._project_combo.addItem(display, path)
        self._project_combo.blockSignals(False)

    def _on_combo_changed(self, index: int) -> None:
        path = self._project_combo.currentData()
        if path:
            self._set_project(Path(path))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Wskaż katalog projektu")
        if path:
            self._set_project(Path(path))

    def _new_project(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dest = dlg.result_path
        name = dlg.project_name
        project_type = dlg.project_type
        try:
            dest.mkdir(parents=True, exist_ok=False)
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się utworzyć folderu:\n{e}")
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        errors = []
        for fname in PROJECT_FILES:
            template = fname.replace(".md", "")
            overrides: dict = {}
            if fname == "CLAUDE.md":
                overrides = {"project": {"name": name, "type": project_type, "client": "", "stack": "Python 3.13+"}}
            elif fname == "PLAN.md":
                overrides = {"meta": {"status": "active", "goal": "", "session": "1", "updated": now}}
            try:
                create_from_template(template, dest / fname, overrides or None)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        if errors:
            QMessageBox.warning(self, "Ostrzeżenie", "Niektóre pliki nie zostały utworzone:\n" + "\n".join(errors))
        display = name or dest.name
        self._project_combo.blockSignals(True)
        self._project_combo.addItem(display, str(dest))
        self._project_combo.blockSignals(False)
        self._set_project(dest)
        self.project_ready.emit(dest)
        QMessageBox.information(self, "Projektant CC", f"Projekt '{name}' utworzony w:\n{dest}")

    def _set_project(self, path: Path) -> None:
        self._project_path = path
        self._path_label.setText(str(path))
        for i in range(self._project_combo.count()):
            if self._project_combo.itemData(i) == str(path):
                self._project_combo.blockSignals(True)
                self._project_combo.setCurrentIndex(i)
                self._project_combo.blockSignals(False)
                break
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        self._file_list.clear()
        self._current_file = None
        self._view_stack.setCurrentIndex(2)  # empty view

        if self._project_path is None:
            for btn in self._create_buttons.values():
                btn.setEnabled(False)
            self._btn_open_editor.setEnabled(False)
            return

        self._btn_open_editor.setEnabled(False)
        for fname in PROJECT_FILES:
            fpath = self._project_path / fname
            item = QListWidgetItem(fname)
            if fpath.exists():
                item.setForeground(Qt.GlobalColor.white)
                item.setToolTip(str(fpath))
                self._create_buttons[fname].setEnabled(False)
            else:
                item.setForeground(Qt.GlobalColor.darkGray)
                item.setToolTip(f"Plik nie istnieje — kliknij '+ {fname}' aby utworzyć")
                self._create_buttons[fname].setEnabled(True)
            self._file_list.addItem(item)

    def _on_file_selected(self, current: QListWidgetItem | None, _prev) -> None:
        self._btn_sss.setChecked(False)
        if current is None or self._project_path is None:
            self._view_stack.setCurrentIndex(2)
            self._current_file = None
            self._btn_open_editor.setEnabled(False)
            return

        fname = current.text()
        fpath = self._project_path / fname

        if not fpath.exists():
            self._view_stack.setCurrentIndex(2)
            self._current_file = None
            self._btn_open_editor.setEnabled(False)
            return

        self._current_file = fpath
        self._btn_open_editor.setEnabled(True)

        if fname == "PLAN.md":
            self._plan_view.load(fpath)
            self._view_stack.setCurrentIndex(0)
        else:
            self._pcc_view.load(fpath)
            self._view_stack.setCurrentIndex(1)

    def _on_view_saved(self, _fname: str) -> None:
        self._refresh_ui()
        # Przywróć selekcję
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item and self._current_file and item.text() == self._current_file.name:
                self._file_list.blockSignals(True)
                self._file_list.setCurrentRow(i)
                self._file_list.blockSignals(False)
                break

    def _create_file(self, template: str, fname: str) -> None:
        if self._project_path is None:
            return
        dest = self._project_path / fname
        if dest.exists():
            QMessageBox.information(self, "Projektant CC", f"{fname} już istnieje.")
            return
        try:
            create_from_template(template, dest)
            self._refresh_ui()
            for i in range(self._file_list.count()):
                if self._file_list.item(i).text() == fname:
                    self._file_list.setCurrentRow(i)
                    break
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie udało się utworzyć {fname}:\n{e}")

    def _open_in_editor(self) -> None:
        if self._current_file and self._current_file.exists():
            subprocess.Popen(["start", "", str(self._current_file)], shell=True)

    def _toggle_sss_panel(self, checked: bool) -> None:
        if checked:
            self._sss_panel.set_project_path(self._project_path)
            self._view_stack.setCurrentIndex(3)
        else:
            self._view_stack.setCurrentIndex(2)
            self._file_list.clearSelection()

    def _on_sss_project_initialized(self, path: Path) -> None:
        self._btn_sss.setChecked(False)
        display = path.name
        already = any(
            self._project_combo.itemData(i) == str(path)
            for i in range(self._project_combo.count())
        )
        if not already:
            self._project_combo.blockSignals(True)
            self._project_combo.addItem(display, str(path))
            self._project_combo.blockSignals(False)
        self._set_project(path)
        self.project_ready.emit(path)
        self._view_stack.setCurrentIndex(2)

    def _open_wizard(self) -> None:
        if self._project_path is None:
            QMessageBox.information(self, "Projektant CC", "Najpierw wskaż lub utwórz projekt.")
            return
        existing = [f for f in PROJECT_FILES if (self._project_path / f).exists()]
        if existing:
            answer = QMessageBox.question(
                self, "Kreator",
                f"Pliki już istnieją:\n{', '.join(existing)}\n\nKreator nadpisze ich zawartość. Kontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        dlg = ProjectWizardDialog(project_name=self._project_path.name, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.result_data
        if not data:
            return
        errors = []
        for fname, file_data in data.items():
            template = fname.replace(".md", "")
            dest = self._project_path / fname
            try:
                overrides = build_overrides(file_data, fname)
                create_from_template(template, dest, overrides or None)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        if errors:
            QMessageBox.warning(self, "Kreator", "Błędy:\n" + "\n".join(errors))
        self._refresh_ui()
        self.project_ready.emit(self._project_path)

    def _open_ai_wizard(self) -> None:
        dlg = AIProjectWizardDialog(self)
        dlg.project_created.connect(self._on_ai_project_created)
        dlg.exec()

    def _on_ai_project_created(self, path: Path) -> None:
        display = path.name
        self._project_combo.blockSignals(True)
        self._project_combo.addItem(display, str(path))
        self._project_combo.blockSignals(False)
        self._set_project(path)
        self.project_ready.emit(path)

    def set_project_path(self, path: Path) -> None:
        self._set_project(path)
