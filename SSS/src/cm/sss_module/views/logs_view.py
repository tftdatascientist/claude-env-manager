from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from src.cm.sss_module.core.log_store import LogStore

logger = logging.getLogger(__name__)


class LogsView(QWidget):
    def __init__(self, store: LogStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # filtry
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Sesja:"))
        self._session_combo = QComboBox()
        self._session_combo.setMinimumWidth(220)
        self._session_combo.currentTextChanged.connect(self._reload)
        filter_row.addWidget(self._session_combo)

        filter_row.addWidget(QLabel("Kind:"))
        self._kind_combo = QComboBox()
        self._kind_combo.addItem("wszystkie", None)
        for k in ("spawn", "round_start", "round_end", "script", "buffer", "task", "milestone", "plan_change", "md_read"):
            self._kind_combo.addItem(k, k)
        self._kind_combo.currentIndexChanged.connect(self._reload)
        filter_row.addWidget(self._kind_combo)
        filter_row.addStretch()
        root.addLayout(filter_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["ts", "round", "kind", "file"])
        self._tree.setColumnWidth(0, 160)
        self._tree.setColumnWidth(1, 50)
        self._tree.setColumnWidth(2, 100)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        splitter.addWidget(self._tree)

        self._payload_view = QPlainTextEdit()
        self._payload_view.setReadOnly(True)
        splitter.addWidget(self._payload_view)
        splitter.setSizes([400, 300])

        root.addWidget(splitter)

    def refresh_sessions(self) -> None:
        current = self._session_combo.currentText()
        self._session_combo.blockSignals(True)
        self._session_combo.clear()
        # unikalne session_id z bazy
        rows = self._store._conn.execute(
            "SELECT DISTINCT session_id FROM events ORDER BY session_id DESC"
        ).fetchall()
        for row in rows:
            self._session_combo.addItem(row[0])
        idx = self._session_combo.findText(current)
        if idx >= 0:
            self._session_combo.setCurrentIndex(idx)
        self._session_combo.blockSignals(False)
        self._reload()

    def _reload(self) -> None:
        self._tree.clear()
        session_id = self._session_combo.currentText()
        if not session_id:
            return
        kind = self._kind_combo.currentData()
        if kind:
            rows = self._store.query_by_kind(kind, session_id=session_id)
        else:
            rows = self._store.query_by_session(session_id)

        for row in rows:
            item = QTreeWidgetItem([
                row.get("ts", ""),
                str(row.get("round") or ""),
                row.get("kind", ""),
                row.get("file_path") or "",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, row.get("payload"))
            self._tree.addTopLevelItem(item)

    def _on_item_selected(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            self._payload_view.clear()
            return
        raw = current.data(0, Qt.ItemDataRole.UserRole)
        if raw:
            try:
                pretty = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, TypeError):
                pretty = str(raw)
        else:
            pretty = ""
        self._payload_view.setPlainText(pretty)

    def append_event(self, row: dict) -> None:
        session_id = self._session_combo.currentText()
        if row.get("session_id") != session_id:
            return
        kind_filter = self._kind_combo.currentData()
        if kind_filter and row.get("kind") != kind_filter:
            return
        item = QTreeWidgetItem([
            row.get("ts", ""),
            str(row.get("round") or ""),
            row.get("kind", ""),
            row.get("file_path") or "",
        ])
        item.setData(0, Qt.ItemDataRole.UserRole, row.get("payload"))
        self._tree.addTopLevelItem(item)
        self._tree.scrollToBottom()
