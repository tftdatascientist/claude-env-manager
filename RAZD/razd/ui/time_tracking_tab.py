from __future__ import annotations

import datetime
from collections import defaultdict
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QDate, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import (
    QCalendarWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository
    from razd.tracker.poller import EventDTO

# kolory dla kategorii (cykl)
_PALETTE = [
    "#4A90D9", "#7ED321", "#F5A623", "#D0021B", "#9013FE",
    "#50E3C2", "#B8E986", "#BD10E0", "#F8E71C", "#417505",
]

_CATEGORY_COLORS: dict[str, str] = {}


def _color_for(category: str) -> str:
    if category not in _CATEGORY_COLORS:
        idx = len(_CATEGORY_COLORS) % len(_PALETTE)
        _CATEGORY_COLORS[category] = _PALETTE[idx]
    return _CATEGORY_COLORS[category]


def _current_hour_fraction() -> float:
    """Aktualny czas jako ułamek godziny (0..24) w bieżącym dniu."""
    now = datetime.datetime.now()
    return now.hour + now.minute / 60 + now.second / 3600


_FOCUS_COLOR = "#9013FE"
_CC_COLOR = "#22aa55"
_CC_STRIP_H = 7


class _TimelineView(QGraphicsView):
    """Oś czasu: 24h — aktywność, bloki focus (nakładka), bloki CC (pasek dolny)."""

    _BAR_H = 32
    _LABEL_W = 4
    _LABEL_AREA = 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFrameShape(self.Shape.NoFrame)
        total_h = self._BAR_H + self._LABEL_AREA + 4
        self.setFixedHeight(total_h)
        self._segments: list[tuple[float, float, str]] = []
        self._focus_blocks: list[tuple[float, float, int]] = []
        # bloki CC: (start_h, end_h, project_name)
        self._cc_blocks: list[tuple[float, float, str]] = []
        self._draw()

    def set_segments(self, segments: list[tuple[float, float, str]]) -> None:
        self._segments = segments
        self._draw()

    def set_focus_blocks(self, blocks: list[tuple[float, float, int]]) -> None:
        self._focus_blocks = blocks
        self._draw()

    def set_cc_blocks(self, blocks: list[tuple[float, float, str]]) -> None:
        self._cc_blocks = blocks
        self._draw()

    def _hour_w(self) -> float:
        """Szerokość jednej godziny w px — dopasowana do aktualnej szerokości widoku."""
        avail = max(self.viewport().width() - self._LABEL_W, 240)
        return avail / 24

    def _draw(self) -> None:
        self._scene.clear()
        hw = self._hour_w()
        W = self._LABEL_W + 24 * hw
        H = self._BAR_H + self._LABEL_AREA + 4
        self._scene.setSceneRect(0, 0, W, H)

        # tło paska
        self._scene.addRect(
            QRectF(self._LABEL_W, 0, 24 * hw, self._BAR_H),
            QPen(Qt.NoPen),
            QBrush(QColor("#222222")),
        )

        # segmenty aktywności
        for start_h, end_h, category in self._segments:
            x = self._LABEL_W + start_h * hw
            w = max((end_h - start_h) * hw, 2.0)
            color = QColor(_color_for(category))
            color.setAlpha(220)
            self._scene.addRect(
                QRectF(x, 2, w, self._BAR_H - 4),
                QPen(Qt.NoPen),
                QBrush(color),
            )

        # linie godzin + etykiety — co 3h, lub co 6h gdy ciasno
        step = 6 if hw < 28 else 3
        font = QFont("Segoe UI", 8)
        font.setWeight(QFont.Weight.Normal)
        label_y = self._BAR_H + 4

        for h in range(25):
            x = self._LABEL_W + h * hw
            pen_color = "#555555" if h % 6 else "#777777"
            self._scene.addLine(x, 0, x, self._BAR_H, QPen(QColor(pen_color), 1))

            if h < 24 and h % step == 0:
                txt = self._scene.addText(f"{h:02d}:00", font)
                txt.setDefaultTextColor(QColor("#bbbbbb"))
                # środkuj etykietę na linii godziny
                txt_w = txt.boundingRect().width()
                txt.setPos(x - txt_w / 2, label_y)

        # bloki CC — dolny pasek aktywności CC (nad segmentami, pod focusem)
        for start_h, end_h, project_name in self._cc_blocks:
            x = self._LABEL_W + start_h * hw
            w = max((end_h - start_h) * hw, 4.0)
            cc_fill = QColor(_CC_COLOR)
            cc_fill.setAlpha(210)
            self._scene.addRect(
                QRectF(x, self._BAR_H - _CC_STRIP_H, w, _CC_STRIP_H),
                QPen(Qt.NoPen),
                QBrush(cc_fill),
            )
            if w >= 36:
                proj = project_name.replace("\\", "/").rstrip("/").split("/")[-1] or project_name
                lbl = f"CC: {proj}"
                font = QFont("Segoe UI", 6)
                txt = self._scene.addText(lbl, font)
                txt.setDefaultTextColor(QColor("#ccffdd"))
                txt.setPos(x + 2, self._BAR_H - _CC_STRIP_H - 1)

        # nakładka bloków focus (nad segmentami aktywności)
        for start_h, end_h, score in self._focus_blocks:
            x = self._LABEL_W + start_h * hw
            w = max((end_h - start_h) * hw, 4.0)
            overlay = QColor(_FOCUS_COLOR)
            overlay.setAlpha(70)
            border = QColor(_FOCUS_COLOR)
            self._scene.addRect(
                QRectF(x, 0, w, self._BAR_H),
                QPen(border, 1),
                QBrush(overlay),
            )
            # pasek u góry (4px) pełny kolor
            self._scene.addRect(
                QRectF(x, 0, w, 4),
                QPen(Qt.NoPen),
                QBrush(border),
            )
            # etykieta score jeśli blok wystarczająco szeroki
            if w >= 32:
                duration_m = round((end_h - start_h) * 60)
                label_txt = f"F {duration_m}m · {score}/10"
                font = QFont("Segoe UI", 7)
                txt = self._scene.addText(label_txt, font)
                txt.setDefaultTextColor(QColor("#ffffff"))
                txt_rect = txt.boundingRect()
                txt.setPos(x + 2, (self._BAR_H - txt_rect.height()) / 2)

        # linia "teraz"
        now_h = _current_hour_fraction()
        if 0 <= now_h <= 24:
            now_x = self._LABEL_W + now_h * hw
            self._scene.addLine(
                now_x, 0, now_x, self._BAR_H,
                QPen(QColor("#FF5252"), 2),
            )

        # resetuj transform — bez fitInView, widok 1:1
        self.resetTransform()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._draw()


class RazdTimeTrackingTab(QWidget):
    """Zakładka Time Tracking — oś czasu, kategorie, statystyki."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo

        # akumulator bieżącej sesji: category → sekundy
        self._session_seconds: dict[str, float] = defaultdict(float)
        # segmenty osi czasu: (start_h, end_h, category)
        self._segments: list[tuple[float, float, str]] = []
        self._last_ts: float | None = None
        self._last_category: str | None = None
        self._focus_blocks: list[tuple[float, float, int]] = []
        self._cc_blocks: list[tuple[float, float, str]] = []
        self._active_cc: dict[str, float] = {}
        # referencja do pollera (ustawiana przez main_window)
        self._poller = None
        # bieżący work_interval_min (zsynchronizowany z break engine)
        self._work_interval_min: int = 50

        self._build_ui()

        # odświeżaj listę kategorii co 30s (zapis przez agenta)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_categories)
        self._refresh_timer.timeout.connect(self._update_break_bar)
        self._refresh_timer.start(30_000)

        self._refresh_categories()

    # -----------------------------------------------------------------
    # Budowa UI
    # -----------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # nagłówek + wybór dnia
        header = QHBoxLayout()
        self._date_label = QLabel(self._today_str())
        self._date_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        btn_today = QPushButton("Dziś")
        btn_today.setFixedWidth(55)
        btn_today.clicked.connect(self._go_today)
        btn_cal = QPushButton("📅")
        btn_cal.setFixedWidth(32)
        btn_cal.clicked.connect(self._toggle_calendar)
        header.addWidget(self._date_label)
        header.addStretch()
        header.addWidget(btn_today)
        header.addWidget(btn_cal)
        root.addLayout(header)

        # kalendarz (ukryty domyślnie)
        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.setMaximumHeight(200)
        self._calendar.selectionChanged.connect(self._on_date_changed)
        self._calendar.hide()
        root.addWidget(self._calendar)

        # pasek przerwy (BreakBar) — nad osią czasu
        break_row = QHBoxLayout()
        self._break_label = QLabel("Praca: 0 min")
        self._break_label.setStyleSheet("color: #5c5; font-size: 11px;")
        self._break_bar = QProgressBar()
        self._break_bar.setRange(0, 50)
        self._break_bar.setValue(0)
        self._break_bar.setTextVisible(False)
        self._break_bar.setFixedHeight(6)
        self._break_bar.setStyleSheet(
            "QProgressBar { background:#333; border-radius:3px; }"
            "QProgressBar::chunk { background:#5c5; border-radius:3px; }"
        )
        self._btn_break = QPushButton("Wzięto przerwę")
        self._btn_break.setFixedWidth(120)
        self._btn_break.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        self._btn_break.clicked.connect(self._on_take_break)
        break_row.addWidget(self._break_label)
        break_row.addWidget(self._break_bar, 1)
        break_row.addWidget(self._btn_break)
        root.addLayout(break_row)

        # oś czasu
        self._timeline = _TimelineView()
        root.addWidget(self._timeline)

        # splitter: status aktywności + lista kategorii
        splitter = QSplitter(Qt.Horizontal)

        # lewo: aktualny status + aktywne sesje CC
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_now = QLabel("Teraz:")
        lbl_now.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(lbl_now)
        self._status = QLabel("Oczekiwanie na dane…")
        self._status.setStyleSheet("color: #ccc; font-size: 12px;")
        self._status.setWordWrap(True)
        left_layout.addWidget(self._status)

        lbl_dist = QLabel("Skupienie:")
        lbl_dist.setStyleSheet("color: #888; font-size: 11px; margin-top: 8px;")
        left_layout.addWidget(lbl_dist)
        self._distraction_label = QLabel("— przełączeń/min")
        self._distraction_label.setStyleSheet("color: #5c5; font-size: 12px;")
        left_layout.addWidget(self._distraction_label)

        lbl_cc = QLabel("Aktywne Claude Code:")
        lbl_cc.setStyleSheet("color: #888; font-size: 11px; margin-top: 8px;")
        left_layout.addWidget(lbl_cc)
        self._cc_list = QListWidget()
        self._cc_list.setMaximumHeight(80)
        self._cc_list.setStyleSheet("color: #22aa55; font-size: 11px;")
        left_layout.addWidget(self._cc_list)

        self._btn_report = QPushButton("📊 Raport dnia")
        self._btn_report.setStyleSheet("font-size: 11px; margin-top: 6px; padding: 4px 8px;")
        self._btn_report.clicked.connect(self._open_report)
        left_layout.addWidget(self._btn_report)
        left_layout.addStretch()
        splitter.addWidget(left)

        # prawo: lista kategorii z czasem
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        lbl_cat = QLabel("Kategorie (dzisiaj):")
        lbl_cat.setStyleSheet("color: #888; font-size: 11px;")
        right_layout.addWidget(lbl_cat)
        self._cat_list = QListWidget()
        self._cat_list.setMaximumWidth(240)
        right_layout.addWidget(self._cat_list)
        splitter.addWidget(right)

        splitter.setSizes([500, 240])
        root.addWidget(splitter)

    # -----------------------------------------------------------------
    # Obsługa eventów ze strumienia trackera
    # -----------------------------------------------------------------

    def on_event(self, dto: EventDTO) -> None:
        now = datetime.datetime.now()

        if dto.event_type == "idle":
            self._status.setText(f"Przerwa ({int(dto.idle_seconds)}s)")
            category = "__idle__"
        else:
            proc = dto.process_name or "—"
            url = f"  ·  {dto.url}" if dto.url else ""
            self._status.setText(f"{proc}{url}")
            category = self._resolve_category(dto)

        # akumulacja czasu
        ts = now.timestamp()
        if self._last_ts is not None and self._last_category is not None:
            elapsed = ts - self._last_ts
            if elapsed < 60:  # ignoruj skoki > 1 min (sleep/hibernate)
                self._session_seconds[self._last_category] += elapsed
                # dodaj segment na oś czasu
                start_h = (ts - elapsed - self._day_start()) / 3600
                end_h = (ts - self._day_start()) / 3600
                if 0 <= start_h < 24 and self._last_category != "__idle__":
                    self._segments.append((start_h, end_h, self._last_category))
                    self._timeline.set_segments(self._segments)

        self._last_ts = ts
        self._last_category = category
        self._update_cat_list()

    def on_cc_session_started(self, project_path: str, session_id: int) -> None:
        """Rejestruje start sesji CC — dodaje do aktywnych i odświeża listę."""
        self._active_cc[project_path] = datetime.datetime.now().timestamp()
        self._refresh_cc_list()

    def on_cc_session_ended(self, project_path: str, duration_s: int) -> None:
        """Rejestruje koniec sesji CC — dodaje blok na osi czasu."""
        started_ts = self._active_cc.pop(project_path, None)
        self._refresh_cc_list()
        if started_ts is None:
            return
        day_start = self._day_start()
        end_ts = datetime.datetime.now().timestamp()
        start_h = (started_ts - day_start) / 3600
        end_h = (end_ts - day_start) / 3600
        if end_h > 0 and start_h < 24:
            proj_name = project_path.replace("\\", "/").rstrip("/").split("/")[-1] or project_path
            self._cc_blocks.append((max(0.0, start_h), min(24.0, end_h), proj_name))
            self._timeline.set_cc_blocks(self._cc_blocks)

    def _refresh_cc_list(self) -> None:
        self._cc_list.clear()
        for path in sorted(self._active_cc):
            proj = path.replace("\\", "/").rstrip("/").split("/")[-1] or path
            item = QListWidgetItem(f"  {proj}")
            from PySide6.QtGui import QColor
            item.setForeground(QColor(_CC_COLOR))
            self._cc_list.addItem(item)

    def set_poller(self, poller) -> None:
        """Ustawia referencję do pollera (dla przycisku przerwy i raportu)."""
        self._poller = poller
        if hasattr(poller, 'break_engine'):
            self._work_interval_min = poller.break_engine.work_interval_min
            self._break_bar.setRange(0, self._work_interval_min)

    def on_break_due(self, minutes_worked: int) -> None:
        """Wołane gdy break engine zgłasza potrzebę przerwy."""
        self._break_label.setText(f"Praca: {minutes_worked} min — CZAS NA PRZERWĘ!")
        self._break_label.setStyleSheet("color: #e55; font-size: 11px; font-weight: bold;")
        self._break_bar.setStyleSheet(
            "QProgressBar { background:#333; border-radius:3px; }"
            "QProgressBar::chunk { background:#e55; border-radius:3px; }"
        )
        self._break_bar.setValue(self._work_interval_min)

    def on_distraction_score(self, spm: float) -> None:
        """Wołane przy każdym pollu — aktualizuje wskaźnik skupienia."""
        spm_r = round(spm, 1)
        if spm_r < 3:
            color, label = "#5c5", "Skupiony"
        elif spm_r < 6:
            color, label = "#c80", "Umiarkowane"
        else:
            color, label = "#e55", "Rozproszony"
        self._distraction_label.setText(f"{spm_r} przełączeń/min — {label}")
        self._distraction_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def on_distraction_alert(self, spm: float) -> None:
        """Wołane przy alertcie o wysokim rozproszeniu."""
        self.on_distraction_score(spm)

    def _on_take_break(self) -> None:
        if self._poller:
            self._poller.confirm_break_taken()
        self._break_label.setText("Praca: 0 min")
        self._break_label.setStyleSheet("color: #5c5; font-size: 11px;")
        self._break_bar.setValue(0)
        self._break_bar.setStyleSheet(
            "QProgressBar { background:#333; border-radius:3px; }"
            "QProgressBar::chunk { background:#5c5; border-radius:3px; }"
        )

    def _update_break_bar(self) -> None:
        if self._poller and hasattr(self._poller, 'break_engine'):
            mins = self._poller.break_engine.worked_minutes
            self._break_bar.setValue(min(mins, self._work_interval_min))
            alerted = self._poller.break_engine._alerted
            if not alerted:
                self._break_label.setText(f"Praca: {mins} min")
                color = "#5c5" if mins < self._work_interval_min * 0.8 else "#c80"
                self._break_label.setStyleSheet(f"color: {color}; font-size: 11px;")
                chunk_color = "#5c5" if mins < self._work_interval_min * 0.8 else "#c80"
                self._break_bar.setStyleSheet(
                    "QProgressBar { background:#333; border-radius:3px; }"
                    f"QProgressBar::chunk {{ background:{chunk_color}; border-radius:3px; }}"
                )

    def _open_report(self) -> None:
        if self._repo is None:
            return
        from razd.ui.report_dialog import RazdDailyReportDialog
        date_str = self._date_label.text()
        try:
            report = self._repo.get_daily_report(date_str)
        except Exception:
            return
        dlg = RazdDailyReportDialog(report, self)
        dlg.exec()

    def on_focus_session(self, started_at: str, ended_at: str, duration_s: int, score: int) -> None:
        """Rejestruje zakończoną sesję focus na osi czasu bieżącego dnia."""
        day_start = self._day_start()
        try:
            s_ts = datetime.datetime.fromisoformat(started_at).timestamp()
            e_ts = datetime.datetime.fromisoformat(ended_at).timestamp()
        except ValueError:
            return
        start_h = (s_ts - day_start) / 3600
        end_h = (e_ts - day_start) / 3600
        if end_h > 0 and start_h < 24:
            self._focus_blocks.append((max(0.0, start_h), min(24.0, end_h), score))
            self._timeline.set_focus_blocks(self._focus_blocks)

    def _resolve_category(self, dto: EventDTO) -> str:
        """Pobiera kategorię z repo lub zwraca nazwę procesu jako fallback."""
        if self._repo is None:
            return dto.process_name or "Inne"
        cat_id: int | None = None
        if dto.url:
            cat_id = self._repo.get_category_for_url(dto.url)
        if cat_id is None and dto.process_name:
            cat_id = self._repo.get_category_for_process(dto.process_name)
        if cat_id is not None:
            cats = self._repo.list_categories()
            for c in cats:
                if c.id == cat_id:
                    return c.name
        return dto.process_name or "Inne"

    # -----------------------------------------------------------------
    # UI helpers
    # -----------------------------------------------------------------

    def _update_cat_list(self) -> None:
        self._cat_list.clear()
        items = sorted(self._session_seconds.items(), key=lambda x: -x[1])
        for cat, secs in items:
            if cat == "__idle__":
                continue
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            item = QListWidgetItem(f"{cat}  —  {h}h {m:02d}m")
            color = QColor(_color_for(cat))
            item.setForeground(color)
            self._cat_list.addItem(item)

    def _refresh_categories(self) -> None:
        """Odświeża kolory kategorii z bazy (jeśli agent dodał nowe)."""
        if self._repo is None:
            return
        for cat in self._repo.list_categories():
            _color_for(cat.name)  # inicjalizuje kolor jeśli brak

    def _toggle_calendar(self) -> None:
        if self._calendar.isHidden():
            self._calendar.show()
        else:
            self._calendar.hide()

    def _go_today(self) -> None:
        self._calendar.setSelectedDate(QDate.currentDate())
        self._calendar.hide()
        self._date_label.setText(self._today_str())
        self._segments = []
        self._focus_blocks = []
        self._cc_blocks = []
        self._session_seconds = defaultdict(float)
        self._timeline.set_segments([])
        self._timeline.set_focus_blocks([])
        self._timeline.set_cc_blocks([])
        self._update_cat_list()

    def _on_date_changed(self) -> None:
        date = self._calendar.selectedDate()
        date_str = date.toString("yyyy-MM-dd")
        self._date_label.setText(date_str)
        self._calendar.hide()
        self._load_day_from_db(date_str)

    def _load_day_from_db(self, date_str: str) -> None:
        """Ładuje historyczny dzień z SQLite i odtwarza oś czasu."""
        if self._repo is None:
            return
        events = self._repo.get_events_for_day(date_str)
        self._segments = []
        acc: dict[str, float] = defaultdict(float)
        cats = {c.id: c for c in self._repo.list_categories()}

        for i, ev in enumerate(events):
            if ev.event_type == "idle" or ev.category_id is None:
                continue
            cat_name = cats[ev.category_id].name if ev.category_id in cats else (ev.process_name or "Inne")
            if i + 1 < len(events):
                next_ts = datetime.datetime.fromisoformat(events[i + 1].ts).timestamp()
            else:
                next_ts = datetime.datetime.fromisoformat(ev.ts).timestamp() + 2
            ev_ts = datetime.datetime.fromisoformat(ev.ts).timestamp()
            day_start = datetime.datetime.fromisoformat(f"{date_str}T00:00:00").timestamp()
            start_h = (ev_ts - day_start) / 3600
            end_h = (next_ts - day_start) / 3600
            if 0 <= start_h < 24:
                self._segments.append((start_h, min(end_h, 24.0), cat_name))
                acc[cat_name] += next_ts - ev_ts

        self._session_seconds = acc

        # załaduj historyczne bloki focus
        self._focus_blocks = []
        day_start_ts = datetime.datetime.fromisoformat(f"{date_str}T00:00:00").timestamp()
        for fs in self._repo.get_focus_sessions_for_day(date_str):
            if fs.ended_at and fs.score is not None:
                try:
                    s_h = (datetime.datetime.fromisoformat(fs.started_at).timestamp() - day_start_ts) / 3600
                    e_h = (datetime.datetime.fromisoformat(fs.ended_at).timestamp() - day_start_ts) / 3600
                    self._focus_blocks.append((max(0.0, s_h), min(24.0, e_h), fs.score))
                except ValueError:
                    pass

        # załaduj historyczne bloki CC
        self._cc_blocks = []
        for cs in self._repo.get_cc_sessions_for_day(date_str):
            if cs.ended_at:
                try:
                    s_h = (datetime.datetime.fromisoformat(cs.started_at).timestamp() - day_start_ts) / 3600
                    e_h = (datetime.datetime.fromisoformat(cs.ended_at).timestamp() - day_start_ts) / 3600
                    proj = cs.project_path.replace("\\", "/").rstrip("/").split("/")[-1] or cs.project_path
                    self._cc_blocks.append((max(0.0, s_h), min(24.0, e_h), proj))
                except ValueError:
                    pass

        self._timeline.set_segments(self._segments)
        self._timeline.set_focus_blocks(self._focus_blocks)
        self._timeline.set_cc_blocks(self._cc_blocks)
        self._update_cat_list()

    @staticmethod
    def _today_str() -> str:
        return datetime.date.today().isoformat()

    @staticmethod
    def _day_start() -> float:
        today = datetime.date.today()
        return datetime.datetime(today.year, today.month, today.day).timestamp()
