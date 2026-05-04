"""Hook Wiki — zakładka z przeglądanką hooks-guide.jsx."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QWidget,
)

from src.hooker.core.wiki_renderer import JSX_PATH, parse_jsx, render_html


_NAV_ITEMS = [
    ("intro",    "📖  Wstęp"),
    ("events",   "⚡  Lifecycle Events"),
    ("handlers", "⚙️  Handler Types"),
    ("control",  "🛡️  Mechanizmy kontroli"),
    ("patterns", "🔀  Wzorce produkcyjne"),
]


class WikiTab(QWidget):
    """Hook Wiki — przeglądarka hooks-guide.jsx z nawigacją sekcji."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._html = ""
        self._setup_ui()
        self._load()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ---- Nawigacja ----
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        self._nav.setStyleSheet(
            "QListWidget { background:#0f172a; border:none; border-right:1px solid #1e293b; }"
            "QListWidget::item { padding:8px 12px; color:#94a3b8; font-size:12px; }"
            "QListWidget::item:selected { background:#1e293b; color:#f8fafc; }"
            "QListWidget::item:hover { background:#1e293b; }"
        )
        for anchor, label in _NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, anchor)
            self._nav.addItem(item)
        self._nav.currentItemChanged.connect(self._on_nav)
        splitter.addWidget(self._nav)

        # ---- Treść ----
        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)  # obsługujemy sami
        self._browser.anchorClicked.connect(self._on_anchor)
        self._browser.setStyleSheet("background:#0f172a; border:none;")
        splitter.addWidget(self._browser)

        splitter.setSizes([180, 820])
        layout.addWidget(splitter)

    # ------------------------------------------------------------------ Load

    def _load(self) -> None:
        if not JSX_PATH.exists():
            self._browser.setHtml(
                "<html><body style='background:#0f172a; color:#ef4444; padding:20px;'>"
                f"<p>Nie znaleziono pliku: <code>{JSX_PATH}</code></p></body></html>"
            )
            return

        self._html = render_html(JSX_PATH)
        self._browser.setHtml(self._html)
        self._nav.setCurrentRow(0)

    # ------------------------------------------------------------------ Navigation

    def _on_nav(self, current: QListWidgetItem | None, _prev: object) -> None:
        if current is None:
            return
        anchor = current.data(Qt.ItemDataRole.UserRole)
        if anchor:
            self._browser.scrollToAnchor(anchor)

    def _on_anchor(self, url: object) -> None:
        """Obsługa kliknięcia linku wewnątrz dokumentu."""
        fragment = str(url.fragment()) if hasattr(url, "fragment") else str(url)
        if fragment:
            self._browser.scrollToAnchor(fragment)
            # Synchronizuj nawigację
            for i in range(self._nav.count()):
                item = self._nav.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == fragment:
                    self._nav.blockSignals(True)
                    self._nav.setCurrentRow(i)
                    self._nav.blockSignals(False)
                    break
