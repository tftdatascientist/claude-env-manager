from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSplitter, QStackedWidget, QTableView, QVBoxLayout, QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository


def _fmt_time(secs: int) -> str:
    h, m = secs // 3600, (secs % 3600) // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m" if m else f"{secs}s"


def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(ts)
        now = datetime.datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d.%m %H:%M")
    except ValueError:
        return ts[:16]


def _make_empty_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color:#555; font-size:12px;")
    lbl.setWordWrap(True)
    return lbl


class RazdWwwTab(QWidget):
    """Zakładka WWW — historia odwiedzonych stron z agregacją per domena."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._view_mode = "domains"   # "domains" | "urls_all" | "search"
        self._selected_domain: str | None = None
        self._date_filter: str | None = datetime.date.today().isoformat()
        self._build_ui()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(30_000)

    # ------------------------------------------------------------------

    def set_repo(self, repo: RazdRepository) -> None:
        self._repo = repo
        self._refresh()

    def notify_new_url(self) -> None:
        """Wołane przez main window po zdarzeniu browser — odświeża liczniki."""
        self._refresh()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── nagłówek ──
        hdr = QHBoxLayout()
        self._stats_lbl = QLabel("Brak danych")
        self._stats_lbl.setStyleSheet("color:#888; font-size:11px;")
        hdr.addWidget(self._stats_lbl)
        hdr.addStretch()

        for label, key in [("Dziś", "today"), ("Tydzień", "week"), ("Wszystko", "all")]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton{font-size:10px;padding:0 6px;border:1px solid #444;"
                "border-radius:3px;background:#2a2a2a;color:#888;}"
                "QPushButton:checked{background:#1565C0;color:#fff;border-color:#1976D2;}"
            )
            btn.clicked.connect(lambda _, k=key: self._set_date_filter(k))
            setattr(self, f"_btn_{key}", btn)
            hdr.addWidget(btn)
        self._btn_today.setChecked(True)
        root.addLayout(hdr)

        # ── search + widok ──
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Szukaj URL, domeny, tytułu…")
        self._search.textChanged.connect(self._on_search)
        self._search.setStyleSheet(
            "QLineEdit{background:#2a2a2a;border:1px solid #444;border-radius:4px;"
            "padding:3px 8px;color:#ddd;font-size:11px;}"
        )
        search_row.addWidget(self._search, 1)

        self._btn_domains = QPushButton("Domeny")
        self._btn_urls_all = QPushButton("Wszystkie URL")
        for btn in (self._btn_domains, self._btn_urls_all):
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton{font-size:10px;padding:0 8px;border:1px solid #444;"
                "border-radius:3px;background:#2a2a2a;color:#888;}"
                "QPushButton:checked{background:#333;color:#fff;border-color:#666;}"
            )
        self._btn_domains.setChecked(True)
        self._btn_domains.clicked.connect(lambda: self._set_view("domains"))
        self._btn_urls_all.clicked.connect(lambda: self._set_view("urls_all"))
        search_row.addWidget(self._btn_domains)
        search_row.addWidget(self._btn_urls_all)
        root.addLayout(search_row)

        # ── splitter: lista główna + panel szczegółów ──
        splitter = QSplitter(Qt.Vertical)

        # górna część: stack (tabela lub placeholder)
        self._main_stack = QStackedWidget()

        self._main_empty_lbl = _make_empty_label(
            "Brak danych o odwiedzonych stronach.\n"
            "Uruchom tracker i otwórz Chrome lub Edge — dane pojawią się automatycznie."
        )
        self._main_stack.addWidget(self._main_empty_lbl)   # index 0 = pusty stan

        self._main_model = QStandardItemModel()
        self._main_proxy = QSortFilterProxyModel()
        self._main_proxy.setSourceModel(self._main_model)
        self._main_proxy.setSortRole(Qt.UserRole)
        self._main_table = QTableView()
        self._main_table.setModel(self._main_proxy)
        self._main_table.setSortingEnabled(True)
        self._main_table.setSelectionBehavior(QTableView.SelectRows)
        self._main_table.setAlternatingRowColors(True)
        self._main_table.verticalHeader().setVisible(False)
        self._main_table.setStyleSheet(
            "QTableView{background:#1e1e1e;alternate-background-color:#222;color:#ccc;"
            "gridline-color:#2a2a2a;font-size:11px;border:none;}"
            "QHeaderView::section{background:#2a2a2a;color:#aaa;padding:4px;"
            "border:none;border-right:1px solid #333;font-size:11px;}"
            "QTableView::item:selected{background:#1565C0;color:#fff;}"
        )
        self._main_table.selectionModel().selectionChanged.connect(self._on_domain_selected)
        self._main_stack.addWidget(self._main_table)        # index 1 = tabela z danymi
        splitter.addWidget(self._main_stack)

        # dolna tabela (URL-e wybranej domeny)
        self._detail_widget = QWidget()
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(0, 4, 0, 0)
        self._detail_lbl = QLabel("Kliknij domenę aby zobaczyć URL-e")
        self._detail_lbl.setStyleSheet("color:#666;font-size:11px;padding:4px;")
        detail_layout.addWidget(self._detail_lbl)
        self._detail_model = QStandardItemModel()
        self._detail_proxy = QSortFilterProxyModel()
        self._detail_proxy.setSourceModel(self._detail_model)
        self._detail_proxy.setSortRole(Qt.UserRole)
        self._detail_table = QTableView()
        self._detail_table.setModel(self._detail_proxy)
        self._detail_table.setSortingEnabled(True)
        self._detail_table.setSelectionBehavior(QTableView.SelectRows)
        self._detail_table.verticalHeader().setVisible(False)
        self._detail_table.setAlternatingRowColors(True)
        self._detail_table.setStyleSheet(self._main_table.styleSheet())
        detail_layout.addWidget(self._detail_table)
        splitter.addWidget(self._detail_widget)

        splitter.setSizes([400, 200])
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------

    def _set_date_filter(self, key: str) -> None:
        today = datetime.date.today()
        if key == "today":
            self._date_filter = today.isoformat()
        elif key == "week":
            self._date_filter = (today - datetime.timedelta(days=6)).isoformat()
        else:
            self._date_filter = None
        self._btn_today.setChecked(key == "today")
        self._btn_week.setChecked(key == "week")
        self._btn_all.setChecked(key == "all")
        self._refresh()

    def _set_view(self, mode: str) -> None:
        self._view_mode = mode
        self._btn_domains.setChecked(mode == "domains")
        self._btn_urls_all.setChecked(mode == "urls_all")
        self._search.clear()
        self._refresh()

    def _on_search(self, text: str) -> None:
        if text.strip():
            self._view_mode = "search"
            self._refresh_search(text.strip())
        else:
            self._view_mode = "domains"
            self._refresh()

    def _on_domain_selected(self) -> None:
        if self._view_mode != "domains":
            return
        indexes = self._main_table.selectionModel().selectedRows()
        if not indexes:
            return
        src_idx = self._main_proxy.mapToSource(indexes[0])
        domain = self._main_model.item(src_idx.row(), 0).text()
        self._selected_domain = domain
        self._refresh_detail(domain)

    def _refresh(self) -> None:
        if self._repo is None:
            self._main_stack.setCurrentIndex(0)
            self._stats_lbl.setText("Brak połączenia z bazą danych")
            return
        if self._view_mode == "domains":
            self._load_domains()
        elif self._view_mode == "urls_all":
            self._load_all_urls()

    def _load_domains(self) -> None:
        domains = self._repo.get_domains(self._date_filter)
        self._main_model.clear()
        self._main_model.setHorizontalHeaderLabels(
            ["Domena", "Unikalne URL", "Wizyty", "Łączny czas", "Ostatnia wizyta", "Przeglądarka"]
        )
        if not domains:
            period = "dziś" if self._date_filter == datetime.date.today().isoformat() else "w wybranym okresie"
            self._main_empty_lbl.setText(
                f"Brak odwiedzonych stron {period}.\n"
                "Upewnij się że tracker działa i masz otwarty Chrome lub Edge."
            )
            self._main_stack.setCurrentIndex(0)
            self._stats_lbl.setText("0 domen")
            return

        total_t = 0
        for d in domains:
            total_t += d.total_time_s
            row = [
                QStandardItem(d.domain),
                self._num_item(d.url_count),
                self._num_item(d.total_visits),
                self._time_item(d.total_time_s),
                self._ts_item(d.last_seen_at),
                QStandardItem(d.browsers or "—"),
            ]
            self._main_model.appendRow(row)
        self._main_stack.setCurrentIndex(1)
        self._main_table.resizeColumnsToContents()
        self._main_table.horizontalHeader().setStretchLastSection(True)
        self._stats_lbl.setText(
            f"{len(domains)} domen · łącznie {_fmt_time(total_t)} online"
        )

    def _load_all_urls(self) -> None:
        if self._repo is None:
            return
        rows_data = self._repo.search_urls("")
        self._populate_url_table(self._main_model, rows_data)
        if not rows_data:
            self._main_empty_lbl.setText(
                "Brak zapisanych URL-i.\n"
                "Upewnij się że tracker działa i masz otwarty Chrome lub Edge."
            )
            self._main_stack.setCurrentIndex(0)
        else:
            self._main_stack.setCurrentIndex(1)
            self._main_table.resizeColumnsToContents()

    def _refresh_search(self, query: str) -> None:
        if self._repo is None:
            return
        results = self._repo.search_urls(query)
        self._populate_url_table(self._main_model, results)
        if not results:
            self._main_empty_lbl.setText(f'Brak wyników dla "{query}".')
            self._main_stack.setCurrentIndex(0)
        else:
            self._main_stack.setCurrentIndex(1)
            self._main_table.resizeColumnsToContents()
        self._stats_lbl.setText(f"Wyniki wyszukiwania: {len(results)} URL")

    def _refresh_detail(self, domain: str) -> None:
        if self._repo is None:
            return
        urls = self._repo.get_urls_for_domain(domain)
        self._detail_lbl.setText(f"URL-e dla {domain} ({len(urls)}):")
        self._populate_url_table(self._detail_model, urls)
        self._detail_table.resizeColumnsToContents()

    def _populate_url_table(self, model: QStandardItemModel, visits) -> None:
        model.clear()
        model.setHorizontalHeaderLabels(
            ["URL", "Tytuł strony", "Wizyty", "Czas", "Pierwsza wizyta", "Ostatnia wizyta", "Przeglądarka"]
        )
        for v in visits:
            row = [
                QStandardItem(v.url),
                QStandardItem(v.page_title or "—"),
                self._num_item(v.visit_count),
                self._time_item(v.total_time_s),
                self._ts_item(v.first_seen_at),
                self._ts_item(v.last_seen_at),
                QStandardItem(v.browser or "—"),
            ]
            model.appendRow(row)

    @staticmethod
    def _num_item(n: int) -> QStandardItem:
        item = QStandardItem(str(n))
        item.setData(n, Qt.UserRole)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    @staticmethod
    def _time_item(secs: int) -> QStandardItem:
        item = QStandardItem(_fmt_time(secs))
        item.setData(secs, Qt.UserRole)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    @staticmethod
    def _ts_item(ts: str) -> QStandardItem:
        item = QStandardItem(_fmt_ts(ts))
        item.setData(ts, Qt.UserRole)
        return item
