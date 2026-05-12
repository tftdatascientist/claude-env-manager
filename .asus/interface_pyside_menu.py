"""ASUS Interface wzorzec: pyside_menu.

Self-contained widget Qt (PySide6) — wstrzykiwany jako zakładka w istniejący
QTabWidget aplikacji-celu. Pisze append-only do ``.asus/notes.jsonl`` w katalogu
aplikacji-celu. Sync z globalnym stanem ASUS robi Adapter (osobny proces).

Nie importuje niczego z `asus.*` — jest niezależnym plikiem do wklejenia.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

NOTES_FILENAME = "notes.jsonl"
ASUS_DIR = ".asus"

_STATUS_PREFIX = {
    "open": "",
    "dispatched": "[->] ",
    "resolved": "[OK] ",
    "dismissed": "[X] ",
}
_STATUS_COLOR = {
    "dispatched": QColor("#b8860b"),
    "resolved":   QColor("#888888"),
    "dismissed":  QColor("#cc4444"),
}

_EDITABLE_FILES = [
    ("README.md",    "README"),
    ("CHANGELOG.md", "Changelog"),
    ("ROADMAP.md",   "Roadmap"),
]


def _load_status_map() -> dict[str, str]:
    data_dir = os.environ.get("ASUS_DATA_DIR", "")
    if not data_dir:
        return {}
    state_path = Path(data_dir) / "asus_state.json"
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return {n["note_id"]: n.get("status", "open") for n in state.get("notes", [])}
    except Exception:
        return {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _format_ts_for_display(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:16]
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _tab_btn_style(active: bool) -> str:
    if active:
        return (
            "QPushButton { font-weight: bold; padding: 4px 16px;"
            " background-color: #e8f0fe; color: #1a56db;"
            " border: 1px solid #93b4f7; border-radius: 3px; }"
        )
    return (
        "QPushButton { padding: 4px 16px; color: #444;"
        " border: 1px solid #ccc; border-radius: 3px; background-color: #f0f0f0; }"
        "QPushButton:hover { background-color: #e4e4e4; }"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Edytor pojedynczego pliku
# ─────────────────────────────────────────────────────────────────────────────

class _FileEditorPanel(QWidget):

    def __init__(self, file_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._dirty = False
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # pasek narzędzi
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._path_lbl = QLabel()
        self._path_lbl.setStyleSheet("color: #555; font-size: 9px;")
        self._path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bar.addWidget(self._path_lbl, 1)

        self._dirty_lbl = QLabel("")
        self._dirty_lbl.setStyleSheet("color: #c80; font-size: 9px; font-weight: bold;")
        bar.addWidget(self._dirty_lbl)

        btn_reload = QPushButton("Odswierz")
        btn_reload.setFixedHeight(22)
        btn_reload.setStyleSheet(
            "QPushButton { font-size: 9px; padding: 0 8px; background: #1e1e1e;"
            " border: 1px solid #333; border-radius: 3px; color: #888; }"
            "QPushButton:hover { background: #252525; color: #bbb; }"
        )
        btn_reload.clicked.connect(self._on_reload)
        bar.addWidget(btn_reload)

        self._btn_save = QPushButton("Zapisz  Ctrl+S")
        self._btn_save.setFixedHeight(22)
        self._btn_save.setStyleSheet(
            "QPushButton { font-size: 9px; padding: 0 10px; background: #1a3a1a;"
            " border: 1px solid #2a6; border-radius: 3px; color: #5c5; font-weight: bold; }"
            "QPushButton:hover { background: #1e441e; }"
            "QPushButton:disabled { color: #383838; border-color: #282828;"
            " background: #141414; }"
        )
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        bar.addWidget(self._btn_save)

        layout.addLayout(bar)

        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setStyleSheet(
            "QTextEdit { background: #0e0e0e; color: #d0d0d0;"
            " border: 1px solid #252525; border-radius: 3px; padding: 6px; }"
        )
        self._editor.setAcceptRichText(False)
        self._editor.textChanged.connect(self._on_changed)
        layout.addWidget(self._editor, 1)

        sc = QShortcut(QKeySequence("Ctrl+S"), self._editor)
        sc.activated.connect(self._on_save)

    def _load(self) -> None:
        self._path_lbl.setText(str(self._file_path))
        text = self._file_path.read_text(encoding="utf-8") if self._file_path.exists() else ""
        self._editor.blockSignals(True)
        self._editor.setPlainText(text)
        self._editor.blockSignals(False)
        self._set_dirty(False)

    def _on_changed(self) -> None:
        if not self._dirty:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._btn_save.setEnabled(dirty)
        self._dirty_lbl.setText("* niezapisane" if dirty else "")

    def _on_save(self) -> None:
        if not self._dirty:
            return
        try:
            self._file_path.write_text(self._editor.toPlainText(), encoding="utf-8")
            self._set_dirty(False)
        except OSError as exc:
            QMessageBox.critical(self, "Blad zapisu", str(exc))

    def _on_reload(self) -> None:
        if self._dirty:
            r = QMessageBox.question(
                self, "Niezapisane zmiany",
                "Odswiezycyi utraci zmiany?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return
        self._load()


# ─────────────────────────────────────────────────────────────────────────────
# Panel Pliki — wybor pliku + edytor
# ─────────────────────────────────────────────────────────────────────────────

class _FilesPanel(QWidget):

    def __init__(self, app_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_root = app_root
        self._panels: list[_FileEditorPanel] = []
        self._btns: list[QPushButton] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # pasek wyboru pliku
        btn_row = QHBoxLayout()
        btn_row.setSpacing(2)
        btn_row.setContentsMargins(4, 4, 4, 0)

        self._file_stack = QStackedWidget()

        for i, (filename, label) in enumerate(_EDITABLE_FILES):
            panel = _FileEditorPanel(self._app_root / filename)
            self._panels.append(panel)
            self._file_stack.addWidget(panel)

            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setFixedHeight(24)
            btn.setStyleSheet(_tab_btn_style(i == 0))
            btn.clicked.connect(lambda _c=False, idx=i: self._switch(idx))
            btn_row.addWidget(btn)
            self._btns.append(btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333;")
        layout.addWidget(sep)

        layout.addWidget(self._file_stack, 1)

    def _switch(self, idx: int) -> None:
        self._file_stack.setCurrentIndex(idx)
        for i, b in enumerate(self._btns):
            b.setChecked(i == idx)
            b.setStyleSheet(_tab_btn_style(i == idx))


# ─────────────────────────────────────────────────────────────────────────────
# Panel Notatki
# ─────────────────────────────────────────────────────────────────────────────

class _NotesPanel(QWidget):

    def __init__(self, notes_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._notes_path = notes_path
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr = QLabel("Notatki ASUS — szybkie zapisanie bledu lub pomyslu")
        hdr.setStyleSheet("font-weight: bold; color: #ccc; font-size: 11px;")
        layout.addWidget(hdr)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Wpisz notatkę i naciśnij Ctrl+Enter…")
        self._input.setMaximumHeight(110)
        layout.addWidget(self._input)

        row = QHBoxLayout()
        btn_add = QPushButton("Dodaj notatkę")
        btn_add.setShortcut("Ctrl+Return")
        btn_add.clicked.connect(self._on_add)
        row.addWidget(btn_add)
        btn_reload = QPushButton("Odswiez")
        btn_reload.clicked.connect(self.reload)
        row.addWidget(btn_reload)
        row.addStretch()
        layout.addLayout(row)

        self._counter = QLabel("0 notatek")
        self._counter.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self._counter)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list, 1)

        lbl = QLabel(f"Plik: {self._notes_path}")
        lbl.setStyleSheet("color: #444; font-size: 9px;")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(lbl)

    def _on_add(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        entry = {"note_id": str(uuid.uuid4()), "timestamp": _now_iso(), "content": text}
        with self._notes_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._input.clear()
        self.reload()

    def reload(self) -> None:
        self._list.clear()
        if not self._notes_path.exists():
            self._counter.setText("0 notatek")
            return
        status_map = _load_status_map()
        entries: list[dict] = []
        for raw in self._notes_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        for entry in entries:
            ts = _format_ts_for_display(entry.get("timestamp", ""))
            content = entry.get("content", "").replace("\n", " / ")
            note_id = entry.get("note_id", "")
            status = status_map.get(note_id, "open")
            prefix = _STATUS_PREFIX.get(status, "")
            item = QListWidgetItem(f"{prefix}[{ts}]  {content}")
            item.setToolTip(entry.get("content", ""))
            color = _STATUS_COLOR.get(status)
            if color:
                item.setForeground(color)
            self._list.addItem(item)
        self._counter.setText(f"{len(entries)} notatek")


# ─────────────────────────────────────────────────────────────────────────────
# Glowna zakladka ASUS
# ─────────────────────────────────────────────────────────────────────────────

class AsusNotesTab(QWidget):
    """Zakladka ASUS: Notatki + edytor plikow projektu."""

    def __init__(self, app_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_root = Path(app_root)
        asus_dir = self._app_root / ASUS_DIR
        asus_dir.mkdir(parents=True, exist_ok=True)
        self._notes_path = asus_dir / NOTES_FILENAME

        # ── glowny layout ────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── pasek sekcji: Notatki | Pliki ────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(2)
        top.setContentsMargins(4, 4, 4, 0)

        self._section_btns: list[QPushButton] = []
        self._main_stack = QStackedWidget()

        for i, label in enumerate(["Notatki", "Pliki (README / Changelog / Roadmap)"]):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setFixedHeight(26)
            btn.setStyleSheet(_tab_btn_style(i == 0))
            btn.clicked.connect(lambda _c=False, idx=i: self._switch(idx))
            top.addWidget(btn)
            self._section_btns.append(btn)

        top.addStretch()
        root.addLayout(top)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #444;")
        root.addWidget(sep)

        # ── strony ──────────────────────────────────────────────────────
        self._notes_panel = _NotesPanel(self._notes_path)
        self._main_stack.addWidget(self._notes_panel)   # index 0

        self._files_panel = _FilesPanel(self._app_root)
        self._main_stack.addWidget(self._files_panel)   # index 1

        root.addWidget(self._main_stack, 1)

        # pierwsze zaladowanie notatek
        self._notes_panel.reload()

    def _switch(self, idx: int) -> None:
        self._main_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._section_btns):
            btn.setChecked(i == idx)
            btn.setStyleSheet(_tab_btn_style(i == idx))

    def reload(self) -> None:
        self._notes_panel.reload()
