from __future__ import annotations

import datetime
import json
import logging

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from razd.db.repository import NotionProjectRow, RazdRepository
from razd.notion.projects_fetcher import NotionProject, NotionProjectsFetcher

logger = logging.getLogger(__name__)

# 4 kolory projektu — zgodne z cc-panel
SLOT_COLORS = ["#7C3AED", "#0EA5E9", "#10B981", "#F59E0B"]
SLOT_NAMES  = ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]

_PRIO_ORDER = {"high": 0, "medium": 1, "low": 2, "": 3, None: 3}


def _prio_key(p: NotionProjectRow) -> int:
    return _PRIO_ORDER.get((p.priority or "").lower(), 2)


def _sort_projects(projects: list[NotionProjectRow]) -> list[NotionProjectRow]:
    return sorted(projects, key=lambda p: (_prio_key(p), p.name.lower()))


def _fmt_hm(secs: int) -> str:
    h, m = secs // 3600, (secs % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


# ──────────────────────────────────────────────────────────────────────────────
# Tło — wątek sync
# ──────────────────────────────────────────────────────────────────────────────

class _SyncThread(QThread):
    done = Signal(int)
    error = Signal(str)

    def __init__(self, fetcher: NotionProjectsFetcher, repo: RazdRepository,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._repo = repo

    def run(self) -> None:
        try:
            projects = self._fetcher.fetch_projects(active_only=False)
            for p in projects:
                self._repo.upsert_notion_project(
                    notion_page_id=p.notion_page_id, name=p.name,
                    status=p.status, priority=p.priority, due_date=p.due_date,
                    raw_properties=json.dumps(p.raw_properties, ensure_ascii=False),
                )
            self.done.emit(len(projects))
        except Exception as exc:
            self.error.emit(str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Karta pinnowanego projektu
# ──────────────────────────────────────────────────────────────────────────────

class _PinnedCard(QFrame):
    """Karta jednego priorytetowego projektu (slot 1-4)."""

    clicked = Signal(int)   # slot (1-4)

    def __init__(self, slot: int, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slot = slot
        self._color = color
        self._project: NotionProjectRow | None = None
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(90)
        self.setMaximumHeight(110)
        self._build()

    def _build(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(3)

        # kolorowy pasek u góry
        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background: {self._color}; border-radius: 2px;")
        self._layout.addWidget(bar)

        self._name_lbl = QLabel("— pusty slot —")
        self._name_lbl.setStyleSheet("color: #555; font-size: 11px; font-style: italic;")
        self._name_lbl.setWordWrap(True)
        self._layout.addWidget(self._name_lbl)

        self._meta_lbl = QLabel("")
        self._meta_lbl.setStyleSheet("color: #555; font-size: 9px;")
        self._layout.addWidget(self._meta_lbl)

        self._time_lbl = QLabel("")
        self._time_lbl.setStyleSheet(f"color: {self._color}; font-size: 10px; font-weight: bold;")
        self._layout.addWidget(self._time_lbl)

        self.setStyleSheet(
            "QFrame { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 6px; }"
            "QFrame:hover { border-color: #3a3a3a; }"
        )
        self.setCursor(Qt.PointingHandCursor)

    def set_project(self, project: NotionProjectRow | None, spent_s: int = 0) -> None:
        self._project = project
        if project is None:
            self._name_lbl.setText("— pusty slot —")
            self._name_lbl.setStyleSheet("color: #555; font-size: 11px; font-style: italic;")
            self._meta_lbl.setText(f"Slot {self._slot}")
            self._time_lbl.setText("")
            self.setStyleSheet(
                "QFrame { background: #1a1a1a; border: 1px solid #222; border-radius: 6px; }"
                "QFrame:hover { border-color: #333; }"
            )
        else:
            self._name_lbl.setText(project.name)
            self._name_lbl.setStyleSheet(f"color: #eee; font-size: 11px; font-weight: bold;")
            meta = []
            if project.status:
                meta.append(project.status)
            if project.due_date:
                meta.append(f"do {project.due_date}")
            self._meta_lbl.setText("  ·  ".join(meta) if meta else "")
            self._time_lbl.setText(_fmt_hm(spent_s) + " łącznie" if spent_s else "0m łącznie")
            self.setStyleSheet(
                f"QFrame {{ background: #1a1a1a; border: 1px solid {self._color}44;"
                f" border-radius: 6px; }}"
                f"QFrame:hover {{ border-color: {self._color}99; background: #1f1f1f; }}"
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._slot)
        super().mousePressEvent(event)

    @property
    def project(self) -> NotionProjectRow | None:
        return self._project

    @property
    def slot(self) -> int:
        return self._slot

    @property
    def color(self) -> str:
        return self._color


# ──────────────────────────────────────────────────────────────────────────────
# Dialog wyboru projektu dla slotu
# ──────────────────────────────────────────────────────────────────────────────

class _SlotPickerDialog(QDialog):
    """Lista aktywnych projektów do przypisania do slotu. Otwiera się po kliknięciu karty."""

    def __init__(
        self,
        projects: list[NotionProjectRow],
        slot: int,
        color: str,
        current: NotionProjectRow | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Slot {slot} — wybierz projekt")
        self.setMinimumSize(420, 460)
        self.setWindowModality(Qt.ApplicationModal)
        self._projects = projects
        self._chosen: NotionProjectRow | None = current   # domyślnie bez zmiany
        self._unpin = False
        self._color = color

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 12, 14, 12)

        # nagłówek z kolorem slotu
        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background: {color}; border-radius: 2px;")
        layout.addWidget(bar)

        hdr = QLabel(f"Wybierz projekt dla <b>Slot {slot}</b>:")
        hdr.setStyleSheet("font-size: 13px; color: #ddd; margin-top: 4px;")
        layout.addWidget(hdr)

        search = QLineEdit()
        search.setPlaceholderText("Szukaj...")
        search.setStyleSheet(
            "QLineEdit { background: #1e1e1e; border: 1px solid #333; border-radius: 4px;"
            " padding: 4px 8px; color: #ddd; font-size: 11px; }"
        )
        layout.addWidget(search)

        self._lst = QListWidget()
        self._lst.setStyleSheet(
            "QListWidget { background: #111; border: 1px solid #222; border-radius: 4px; }"
            "QListWidget::item { padding: 5px 8px; color: #ccc; font-size: 11px; }"
            "QListWidget::item:selected { background: #1e2a3a; color: #fff; }"
        )
        self._lst.itemDoubleClicked.connect(self._accept_selection)
        layout.addWidget(self._lst, 1)

        self._populate(projects)
        if current:
            # zaznacz aktualnie przypisany
            for i in range(self._lst.count()):
                item = self._lst.item(i)
                if item and item.data(Qt.UserRole) and item.data(Qt.UserRole).id == current.id:
                    self._lst.setCurrentRow(i)
                    break

        search.textChanged.connect(self._filter)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Przypisz")
        btn_ok.setStyleSheet(
            f"QPushButton {{ background: {color}; color: #fff; font-weight: bold;"
            f" padding: 6px 20px; border-radius: 5px; border: none; }}"
            f"QPushButton:hover {{ opacity: 0.85; }}"
        )
        btn_ok.clicked.connect(self._accept_selection)
        btns.addWidget(btn_ok)

        if current:
            btn_unpin = QPushButton("Odepnij slot")
            btn_unpin.setStyleSheet(
                "QPushButton { color: #c55; padding: 6px 14px; background: #1a1a1a;"
                " border: 1px solid #c5533a; border-radius: 5px; }"
                "QPushButton:hover { background: #2a1a1a; }"
            )
            btn_unpin.clicked.connect(self._do_unpin)
            btns.addWidget(btn_unpin)

        btns.addStretch()
        btn_cancel = QPushButton("Anuluj")
        btn_cancel.setStyleSheet("color: #555; padding: 6px 10px;")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _populate(self, projects: list[NotionProjectRow]) -> None:
        self._lst.clear()
        for p in projects:
            label = p.name
            if p.due_date:
                label += f"   do {p.due_date}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, p)
            self._lst.addItem(item)

    def _filter(self, text: str) -> None:
        q = text.lower()
        self._populate([p for p in self._projects if q in p.name.lower()])

    def _accept_selection(self) -> None:
        item = self._lst.currentItem()
        if item:
            self._chosen = item.data(Qt.UserRole)
            self._unpin = False
            self.accept()

    def _do_unpin(self) -> None:
        self._chosen = None
        self._unpin = True
        self.accept()

    def chosen_project(self) -> NotionProjectRow | None:
        """None = odepnij; NotionProjectRow = przypisz."""
        return None if self._unpin else self._chosen


# ──────────────────────────────────────────────────────────────────────────────
# Zakładka Projekty
# ──────────────────────────────────────────────────────────────────────────────

class RazdProjectsTab(QWidget):

    pinned_changed = Signal()   # emitowany po zmianie przypiętych projektów

    def __init__(self, repo: RazdRepository, fetcher: NotionProjectsFetcher | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._fetcher = fetcher
        self._sync_thread: _SyncThread | None = None
        self._all_projects: list[NotionProjectRow] = []
        self._selected_project: NotionProjectRow | None = None
        self._build_ui()
        self._load_local_projects()

    # ── budowa UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(6, 6, 6, 6)

        # ── pasek górny ───────────────────────────────────────────────────
        top = QHBoxLayout()
        title = QLabel("Projekty Notion")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        top.addWidget(title)
        top.addStretch()
        self._sync_btn = QPushButton("↻ Synchronizuj z Notion")
        self._sync_btn.setEnabled(bool(self._fetcher and self._fetcher.is_configured()))
        self._sync_btn.clicked.connect(self._on_sync)
        top.addWidget(self._sync_btn)
        root.addLayout(top)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #666; font-size: 10px;")
        root.addWidget(self._status_lbl)

        # ── 4 karty priorytetowe ──────────────────────────────────────────
        pinned_group = QGroupBox("Projekty priorytetowe")
        pinned_group.setStyleSheet(
            "QGroupBox { font-size: 11px; color: #888; border: 1px solid #2a2a2a;"
            " border-radius: 6px; margin-top: 6px; padding-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )
        pinned_layout = QHBoxLayout(pinned_group)
        pinned_layout.setSpacing(8)
        pinned_layout.setContentsMargins(8, 12, 8, 8)

        self._cards: list[_PinnedCard] = []
        for i, color in enumerate(SLOT_COLORS):
            card = _PinnedCard(slot=i + 1, color=color)
            card.clicked.connect(self._on_card_clicked)   # slot (int)
            self._cards.append(card)
            pinned_layout.addWidget(card)

        root.addWidget(pinned_group)

        hint_lbl = QLabel("Kliknij slot żeby przypisać projekt  ·  kliknij zajęty slot żeby zmienić lub odpiąć")
        hint_lbl.setStyleSheet("color: #3a3a3a; font-size: 9px;")
        root.addWidget(hint_lbl)

        root.addWidget(pinned_group)

        # ── główny splitter: lista + szczegóły ───────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # lewa — lista + wyszukiwanie
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Szukaj projektu...")
        self._search.textChanged.connect(self._filter_list)
        self._search.setStyleSheet(
            "QLineEdit { background: #1e1e1e; border: 1px solid #333; border-radius: 4px;"
            " padding: 4px 8px; color: #ddd; font-size: 11px; }"
        )
        left_layout.addWidget(self._search)

        self._project_list = QListWidget()
        self._project_list.currentItemChanged.connect(self._on_list_selected)
        self._project_list.setStyleSheet(
            "QListWidget { background: #111; border: 1px solid #222; border-radius: 4px; }"
            "QListWidget::item { padding: 4px 6px; color: #ccc; font-size: 11px; }"
            "QListWidget::item:selected { background: #1e2a3a; color: #fff; }"
        )
        left_layout.addWidget(self._project_list, 1)

        splitter.addWidget(left)

        # prawa — szczegóły
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._detail_widget = _ProjectDetailWidget(self._repo)
        right_scroll.setWidget(self._detail_widget)
        splitter.addWidget(right_scroll)

        splitter.setSizes([260, 600])
        root.addWidget(splitter, 1)


    # ── ładowanie danych ─────────────────────────────────────────────────────

    def _load_local_projects(self) -> None:
        self._all_projects = _sort_projects(self._repo.list_notion_projects(active_only=True))
        self._refresh_list(self._all_projects)
        self._refresh_pinned_cards()

        count = len(self._all_projects)
        sync_ts = self._all_projects[0].synced_at[:16] if self._all_projects else "—"
        self._status_lbl.setText(
            f"In Progress: {count}  |  sync: {sync_ts}"
        )

    def _refresh_list(self, projects: list[NotionProjectRow]) -> None:
        self._project_list.clear()
        pinned_ids = {p.id for _, p, _ in self._repo.get_pinned_projects()}
        for p in projects:
            label = p.name
            if p.due_date:
                label += f"   do {p.due_date}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, p)
            if p.id in pinned_ids:
                # kolor tekstu dopasowany do slotu
                for slot, pp, color in self._repo.get_pinned_projects():
                    if pp.id == p.id:
                        item.setForeground(QColor(color))
                        break
            self._project_list.addItem(item)

    def _refresh_pinned_cards(self) -> None:
        pinned = {slot: (proj, color) for slot, proj, color in self._repo.get_pinned_projects()}
        for card in self._cards:
            if card.slot in pinned:
                proj, color = pinned[card.slot]
                stats = self._repo.get_project_time_stats(proj.id)
                spent_s = sum(stats.values())
                card.set_project(proj, spent_s)
            else:
                card.set_project(None)

    def _filter_list(self, text: str) -> None:
        q = text.lower()
        filtered = [p for p in self._all_projects if q in p.name.lower()]
        self._refresh_list(filtered)

    # ── wybór projektu ───────────────────────────────────────────────────────

    def _on_list_selected(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if not current:
            return
        project: NotionProjectRow = current.data(Qt.UserRole)
        self._selected_project = project
        self._detail_widget.show_project(project)

    def _on_card_clicked(self, slot: int) -> None:
        """Otwiera dialog wyboru projektu dla danego slotu."""
        card = self._cards[slot - 1]
        color = SLOT_COLORS[slot - 1]
        dlg = _SlotPickerDialog(
            projects=self._all_projects,
            slot=slot,
            color=color,
            current=card.project,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.chosen_project()
            if chosen is None:
                # odepnij
                self._repo.clear_pinned_slot(slot)
            else:
                self._repo.set_pinned_project(slot, chosen.id, color)
            self._refresh_pinned_cards()
            self._refresh_list(self._all_projects)
            self.pinned_changed.emit()

    # ── sync Notion ──────────────────────────────────────────────────────────

    def _on_sync(self) -> None:
        if not self._fetcher or not self._fetcher.is_configured():
            self._status_lbl.setText("Notion nie skonfigurowany (brak RAZD_NOTION_PROJECTS_DB_ID)")
            return
        if self._sync_thread and self._sync_thread.isRunning():
            return
        self._sync_btn.setEnabled(False)
        self._status_lbl.setText("Synchronizuję...")
        self._sync_thread = _SyncThread(self._fetcher, self._repo, self)
        self._sync_thread.done.connect(self._on_sync_done)
        self._sync_thread.error.connect(self._on_sync_error)
        self._sync_thread.start()

    def _on_sync_done(self, count: int) -> None:
        self._sync_btn.setEnabled(True)
        self._status_lbl.setText(f"Zsynchronizowano {count} projektów")
        self._status_lbl.setStyleSheet("color: #5c5; font-size: 10px;")
        self._load_local_projects()

    def _on_sync_error(self, msg: str) -> None:
        self._sync_btn.setEnabled(True)
        self._status_lbl.setText(f"Błąd: {msg[:100]}")
        self._status_lbl.setStyleSheet("color: #c55; font-size: 10px;")

    def refresh(self) -> None:
        self._load_local_projects()
        if self._selected_project:
            self._detail_widget.show_project(self._selected_project)


# ──────────────────────────────────────────────────────────────────────────────
# Panel szczegółów projektu
# ──────────────────────────────────────────────────────────────────────────────

class _ProjectDetailWidget(QWidget):
    """Prawy panel — info, szczegółowe pomiary czasu, historia sesji."""

    def __init__(self, repo: RazdRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(8)

        # ── info ────────────────────────────────────────────────────────
        info_box = QGroupBox("Projekt")
        info_layout = QVBoxLayout(info_box)
        self._info_browser = QTextBrowser()
        self._info_browser.setMaximumHeight(100)
        self._info_browser.setStyleSheet(
            "QTextBrowser { background: #111; border: none; color: #ccc; font-size: 11px; }"
        )
        info_layout.addWidget(self._info_browser)
        layout.addWidget(info_box)

        # ── statystyki czasu (łącznie / dziś / tydzień / miesiąc) ───────
        stats_box = QGroupBox("Czas — pomiary szczegółowe")
        stats_grid = QHBoxLayout(stats_box)
        stats_grid.setSpacing(6)
        stats_grid.setContentsMargins(10, 14, 10, 10)

        self._stat_labels: dict[str, QLabel] = {}
        periods = [
            ("today",   "Dziś",      "#5BA8F5", "#1a2a3a"),
            ("week",    "Ten tydzień","#34D399", "#1a2e28"),
            ("month",   "Ten miesiąc","#FBBF24", "#2a2416"),
            ("total",   "Łącznie",   "#A78BFA", "#221a33"),
        ]
        for col, (key, label, color, bg) in enumerate(periods):
            cell = QFrame()
            cell.setStyleSheet(
                f"QFrame {{ background: {bg}; border-radius: 5px; border: 1px solid {color}44; }}"
            )
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(6, 5, 6, 5)
            cell_layout.setSpacing(2)

            h = QLabel(label)
            h.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold;")
            h.setAlignment(Qt.AlignCenter)
            cell_layout.addWidget(h)

            v = QLabel("—")
            v.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            v.setAlignment(Qt.AlignCenter)
            cell_layout.addWidget(v)
            self._stat_labels[key] = v

            stats_grid.addWidget(cell)

        layout.addWidget(stats_box)

        # ── historia sesji ───────────────────────────────────────────────
        sess_box = QGroupBox("Sesje focus")
        sess_layout = QVBoxLayout(sess_box)
        self._sessions_list = QListWidget()
        self._sessions_list.setStyleSheet(
            "QListWidget { background: #111; border: none; font-size: 10px; }"
            "QListWidget::item { padding: 3px 6px; color: #aaa; }"
            "QListWidget::item:alternate { background: #161616; }"
        )
        self._sessions_list.setAlternatingRowColors(True)
        sess_layout.addWidget(self._sessions_list)
        layout.addWidget(sess_box, 1)

    def show_project(self, project: NotionProjectRow) -> None:
        # ── info ────────────────────────────────────────────────────────
        lines = [f"<b style='font-size:13px;'>{project.name}</b>"]
        if project.status:
            lines.append(f"Status: <b>{project.status}</b>")
        if project.priority:
            lines.append(f"Priorytet: <b>{project.priority}</b>")
        if project.due_date:
            lines.append(f"Termin: <b>{project.due_date}</b>")
        self._info_browser.setHtml("<br>".join(lines))

        # ── statystyki ──────────────────────────────────────────────────
        stats = self._repo.get_project_time_stats(project.id)
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        month_str = today.strftime("%Y-%m")

        today_s = stats.get(today.isoformat(), 0)
        week_s = sum(s for d, s in stats.items()
                     if d >= week_start.isoformat())
        month_s = sum(s for d, s in stats.items()
                      if d.startswith(month_str))
        total_s = sum(stats.values())

        self._stat_labels["today"].setText(_fmt_hm(today_s) if today_s else "—")
        self._stat_labels["week"].setText(_fmt_hm(week_s) if week_s else "—")
        self._stat_labels["month"].setText(_fmt_hm(month_s) if month_s else "—")
        self._stat_labels["total"].setText(_fmt_hm(total_s) if total_s else "—")

        # ── sesje ────────────────────────────────────────────────────────
        self._sessions_list.clear()
        rows = self._repo._conn.execute(
            "SELECT fs.started_at, fs.ended_at, fs.duration_s, fs.score, fsp.notion_synced"
            " FROM focus_session_project fsp"
            " JOIN focus_sessions fs ON fs.id = fsp.session_id"
            " WHERE fsp.notion_project_id=? AND fs.ended_at IS NOT NULL"
            " ORDER BY fs.started_at DESC LIMIT 50",
            (project.id,),
        ).fetchall()

        if not rows:
            self._sessions_list.addItem("Brak sesji focus dla tego projektu")
            return

        for r in rows:
            started = r[0][:16]
            dur_m = r[2] // 60
            score = r[3]
            synced = r[4]
            score_str = f"  wynik {score}/10" if score is not None else ""
            sync_str = "  ✓" if synced else ""
            self._sessions_list.addItem(f"{started}   {dur_m}m{score_str}{sync_str}")

        total_m = sum(r[2] for r in rows) // 60
        total_item = QListWidgetItem(f"── {len(rows)} sesji  ·  {total_m}m łącznie ──")
        total_item.setForeground(QColor("#555"))
        self._sessions_list.addItem(total_item)
