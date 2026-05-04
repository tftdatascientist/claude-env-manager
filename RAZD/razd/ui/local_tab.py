from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSplitter,
    QTableView, QVBoxLayout, QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository

_CC_PROCESSES = frozenset({"cc.exe", "cc", "claude.exe", "claude"})
_VSCODE_PROCESSES = frozenset({"code.exe", "code", "cursor.exe", "cursor"})
_BROWSER_PROCESSES = frozenset({"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"})


def _fmt_time(secs: int) -> str:
    h, m = secs // 3600, (secs % 3600) // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m" if m else f"{secs}s"


def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(ts)
        now = datetime.datetime.now()
        diff = (now - dt).total_seconds()
        if diff < 60:
            return "przed chwilą"
        if diff < 3600:
            return f"{int(diff/60)} min temu"
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d.%m %H:%M")
    except ValueError:
        return ts[:16]


def _process_type(name: str) -> str:
    low = name.lower()
    if low in _CC_PROCESSES:
        return "CC"
    if low in _VSCODE_PROCESSES:
        return "IDE"
    if low in _BROWSER_PROCESSES:
        return "Browser"
    return "Dev" if any(d in low for d in ("python", "node", "git", "cmd", "powershell", "wt.exe")) else "App"


def _process_color(name: str) -> str:
    t = _process_type(name)
    return {"CC": "#22aa55", "IDE": "#4A90D9", "Browser": "#F5A623", "Dev": "#C792EA"}.get(t, "#888")


class RazdLocalTab(QWidget):
    """Zakładka Local — śledzenie lokalnych aplikacji ze szczególnym uwzględnieniem narzędzi dev."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._filter = "all"
        self._current_process: str | None = None
        self._build_ui()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(15_000)

    # ------------------------------------------------------------------

    def set_repo(self, repo: RazdRepository) -> None:
        self._repo = repo
        self._refresh()

    def on_event(self, dto) -> None:
        """Wołane przez main_window przy każdym pollu — aktualizuje aktywny proces."""
        if dto.event_type != "idle":
            self._current_process = dto.process_name
            self._update_active_label()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── nagłówek ──
        hdr = QHBoxLayout()
        self._stats_lbl = QLabel("Ładowanie…")
        self._stats_lbl.setStyleSheet("color:#888;font-size:11px;")
        hdr.addWidget(self._stats_lbl)
        hdr.addStretch()
        self._active_lbl = QLabel("Aktywny: —")
        self._active_lbl.setStyleSheet("color:#5c5;font-size:11px;")
        hdr.addWidget(self._active_lbl)
        root.addLayout(hdr)

        # ── filtry ──
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtr:"))
        for label, key in [
            ("Wszystkie", "all"),
            ("Dev Tools", "dev"),
            ("CC", "cc"),
            ("IDE", "ide"),
            ("Browser", "browser"),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton{font-size:10px;padding:0 6px;border:1px solid #444;"
                "border-radius:3px;background:#2a2a2a;color:#888;}"
                "QPushButton:checked{background:#1565C0;color:#fff;border-color:#1976D2;}"
            )
            btn.clicked.connect(lambda _, k=key: self._set_filter(k))
            setattr(self, f"_filter_btn_{key}", btn)
            filter_row.addWidget(btn)
        self._filter_btn_all.setChecked(True)
        filter_row.addStretch()
        root.addLayout(filter_row)

        # ── splitter: tabela aplikacji + panel CC ──
        splitter = QSplitter(Qt.Vertical)

        # tabela aplikacji
        self._model = QStandardItemModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.UserRole)
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            "QTableView{background:#1e1e1e;alternate-background-color:#222;color:#ccc;"
            "gridline-color:#2a2a2a;font-size:11px;border:none;}"
            "QHeaderView::section{background:#2a2a2a;color:#aaa;padding:4px;"
            "border:none;border-right:1px solid #333;font-size:11px;}"
            "QTableView::item:selected{background:#1565C0;color:#fff;}"
        )
        splitter.addWidget(self._table)

        # panel CC sessions
        cc_panel = QWidget()
        cc_layout = QVBoxLayout(cc_panel)
        cc_layout.setContentsMargins(0, 4, 0, 0)
        cc_layout.setSpacing(4)
        self._cc_header_lbl = QLabel("Sesje Claude Code — dziś:")
        self._cc_header_lbl.setStyleSheet("color:#22aa55;font-size:11px;font-weight:bold;")
        cc_layout.addWidget(self._cc_header_lbl)
        self._cc_model = QStandardItemModel()
        self._cc_table = QTableView()
        self._cc_table.setModel(self._cc_model)
        self._cc_table.setSelectionBehavior(QTableView.SelectRows)
        self._cc_table.verticalHeader().setVisible(False)
        self._cc_table.setAlternatingRowColors(True)
        self._cc_table.setStyleSheet(self._table.styleSheet())
        cc_layout.addWidget(self._cc_table)
        splitter.addWidget(cc_panel)

        splitter.setSizes([500, 180])
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------

    def _set_filter(self, key: str) -> None:
        self._filter = key
        for k in ("all", "dev", "cc", "ide", "browser"):
            getattr(self, f"_filter_btn_{k}").setChecked(k == key)
        self._refresh()

    def _update_active_label(self) -> None:
        if self._current_process:
            color = _process_color(self._current_process)
            self._active_lbl.setText(f"Aktywny: {self._current_process}")
            self._active_lbl.setStyleSheet(f"color:{color};font-size:11px;font-weight:bold;")

    def _refresh(self) -> None:
        if self._repo is None:
            return
        self._load_apps()
        self._load_cc_sessions()

    def _load_apps(self) -> None:
        dev_only = self._filter == "dev"
        apps = self._repo.get_app_usage_list(dev_only=dev_only)

        # apply additional filter
        if self._filter == "cc":
            apps = [a for a in apps if a.process_name.lower() in _CC_PROCESSES]
        elif self._filter == "ide":
            apps = [a for a in apps if a.process_name.lower() in _VSCODE_PROCESSES]
        elif self._filter == "browser":
            apps = [a for a in apps if a.process_name.lower() in _BROWSER_PROCESSES]

        self._model.clear()
        self._model.setHorizontalHeaderLabels([
            "Proces", "Typ", "Dziś", "Łącznie", "Przełączeń",
            "Pierwsza wizyta", "Ostatnia aktywność",
        ])

        total_today = 0
        for app in apps:
            ptype = _process_type(app.process_name)
            color = _process_color(app.process_name)

            name_item = QStandardItem(app.process_name)
            name_item.setForeground(QColor(color))

            type_item = QStandardItem(ptype)
            type_item.setForeground(QColor(color))
            type_item.setTextAlignment(Qt.AlignCenter)

            today_item = self._time_item(app.today_time_s)
            total_item = self._time_item(app.total_time_s)
            switches_item = self._num_item(app.focus_switches)

            first_item = QStandardItem(_fmt_ts(app.first_seen_at))
            last_item = QStandardItem(_fmt_ts(app.last_seen_at))

            # mark currently active
            if (self._current_process and
                    self._current_process.lower() == app.process_name.lower()):
                for it in (name_item, type_item):
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                last_item.setText("AKTYWNY")
                last_item.setForeground(QColor("#5c5"))

            self._model.appendRow([name_item, type_item, today_item, total_item,
                                    switches_item, first_item, last_item])
            total_today += app.today_time_s

        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)

        dev_count = sum(1 for a in apps if a.is_dev_tool)
        self._stats_lbl.setText(
            f"{len(apps)} aplikacji · {dev_count} dev tools · {_fmt_time(total_today)} dziś"
        )

    def _load_cc_sessions(self) -> None:
        if self._repo is None:
            return
        today = datetime.date.today().isoformat()
        sessions = self._repo.get_cc_sessions_for_day(today)

        self._cc_model.clear()
        self._cc_model.setHorizontalHeaderLabels(
            ["Projekt", "Start", "Koniec", "Czas trwania", "Status"]
        )
        for s in sessions:
            proj = s.project_path.replace("\\", "/").rstrip("/").split("/")[-1] or s.project_path
            start = s.started_at[11:16]
            end = s.ended_at[11:16] if s.ended_at else "—"
            dur = _fmt_time(s.duration_s)
            status = "zakończona" if s.ended_at else "AKTYWNA"
            status_color = "#22aa55" if not s.ended_at else "#888"

            proj_item = QStandardItem(proj)
            proj_item.setForeground(QColor("#22aa55"))
            status_item = QStandardItem(status)
            status_item.setForeground(QColor(status_color))
            if not s.ended_at:
                f = status_item.font()
                f.setBold(True)
                status_item.setFont(f)

            self._cc_model.appendRow([
                proj_item,
                QStandardItem(start),
                QStandardItem(end),
                QStandardItem(dur),
                status_item,
            ])
        self._cc_table.resizeColumnsToContents()
        self._cc_header_lbl.setText(f"Sesje Claude Code — dziś ({len(sessions)}):")

    @staticmethod
    def _time_item(secs: int) -> QStandardItem:
        item = QStandardItem(_fmt_time(secs))
        item.setData(secs, Qt.UserRole)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    @staticmethod
    def _num_item(n: int) -> QStandardItem:
        item = QStandardItem(str(n))
        item.setData(n, Qt.UserRole)
        item.setTextAlignment(Qt.AlignCenter)
        return item
