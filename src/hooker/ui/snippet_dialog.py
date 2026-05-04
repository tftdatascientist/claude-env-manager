"""SnippetDialog — picker snippetów z podglądem."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.hooker.core.snippet_manager import Snippet, snippets_for_type


class SnippetDialog(QDialog):
    """Dialog wyboru snippetu dla danego typu hooka."""

    def __init__(self, hook_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hook_type = hook_type
        self._snippets: list[Snippet] = []
        self._selected: Snippet | None = None
        self.setWindowTitle(f"Wstaw snippet — {hook_type}")
        self.resize(700, 380)
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel(
            f"<b>Snippety dla <span style='color:#3b82f6'>{self._hook_type}</span></b>"
            f"<span style='color:#64748b'> — wbudowane + user override</span>"
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Lista snippetów
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.addWidget(QLabel("Dostępne snippety:"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self._list)
        splitter.addWidget(left)

        # Podgląd
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.addWidget(QLabel("Podgląd:"))
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet("font-family: monospace; font-size: 11px; background:#1e293b;")
        right_layout.addWidget(self._preview)
        splitter.addWidget(right)

        splitter.setSizes([280, 400])
        layout.addWidget(splitter, 1)

        btns = QDialogButtonBox()
        self._btn_insert = btns.addButton("✅ Wstaw", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_insert.setEnabled(False)
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._do_insert)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._snippets = snippets_for_type(self._hook_type)
        self._list.clear()

        if not self._snippets:
            item = QListWidgetItem(f"(brak snippetów dla {self._hook_type})")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            return

        for s in self._snippets:
            tags_str = "  " + " ".join(f"[{t}]" for t in s.tags) if s.tags else ""
            item = QListWidgetItem(f"{s.name}{tags_str}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self._list.addItem(item)

        self._list.setCurrentRow(0)

    def _on_select(self, current: QListWidgetItem | None, _prev: object) -> None:
        if current is None:
            self._preview.setPlainText("")
            self._btn_insert.setEnabled(False)
            return

        s: Snippet | None = current.data(Qt.ItemDataRole.UserRole)
        if s is None:
            self._preview.setPlainText("")
            self._btn_insert.setEnabled(False)
            return

        lines = [
            f"Nazwa:    {s.name}",
            f"Typ:      {s.hook_type}",
            f"Matcher:  {s.matcher or '(brak — wszystkie narzędzia)'}",
            f"Command:  {s.command}",
            f"",
            f"Opis:",
            s.description,
        ]
        if s.tags:
            lines.append(f"\nTagi: {', '.join(s.tags)}")
        self._preview.setPlainText("\n".join(lines))
        self._btn_insert.setEnabled(True)
        self._selected = s

    def _do_insert(self) -> None:
        if self._selected is not None:
            self.accept()

    def get_snippet(self) -> Snippet | None:
        return self._selected
