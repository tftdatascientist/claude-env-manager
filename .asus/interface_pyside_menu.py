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
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

NOTES_FILENAME = "notes.jsonl"
ASUS_DIR = ".asus"

_STATUS_PREFIX = {
    "open": "",
    "dispatched": "[→] ",
    "resolved": "[✓] ",
    "dismissed": "[✗] ",
}
_STATUS_COLOR = {
    "dispatched": QColor("#b8860b"),
    "resolved": QColor("#888888"),
    "dismissed": QColor("#cc4444"),
}


def _load_status_map() -> dict[str, str]:
    """Wczytaj {note_id: status} z globalnego asus_state.json (jeśli dostępny)."""
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


class AsusNotesTab(QWidget):
    """Zakładka notatek ASUS — wstrzykuj do QTabWidget aplikacji-celu.

    Parametry:
        app_root: katalog aplikacji-celu (tam powstaje ``.asus/notes.jsonl``).
    """

    def __init__(self, app_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._asus_dir = Path(app_root) / ASUS_DIR
        self._asus_dir.mkdir(parents=True, exist_ok=True)
        self._notes_path = self._asus_dir / NOTES_FILENAME
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("Notatki ASUS — szybkie zapisanie błędu lub pomysłu")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        self._input = QTextEdit()
        self._input.setPlaceholderText(
            "Wpisz notatkę o błędzie lub ulepszeniu i naciśnij Ctrl+Enter…"
        )
        self._input.setMaximumHeight(120)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        button_row = QHBoxLayout()
        self._btn_add = QPushButton("Dodaj notatkę")
        self._btn_add.setShortcut("Ctrl+Return")
        self._btn_add.clicked.connect(self._on_add)
        button_row.addWidget(self._btn_add)

        self._btn_reload = QPushButton("Odśwież")
        self._btn_reload.clicked.connect(self.reload)
        button_row.addWidget(self._btn_reload)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._counter = QLabel("0 notatek")
        layout.addWidget(self._counter)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list, 1)

        path_label = QLabel(f"Plik: {self._notes_path}")
        path_label.setStyleSheet("color: gray; font-size: 10px;")
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(path_label)

    def _on_add(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        entry = {
            "note_id": str(uuid.uuid4()),
            "timestamp": _now_iso(),
            "content": text,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._notes_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
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
            content = entry.get("content", "").replace("\n", " ⏎ ")
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
