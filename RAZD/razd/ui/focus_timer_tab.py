from __future__ import annotations

import datetime
import math
import threading
from collections import Counter
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository
    from razd.notion.projects_fetcher import NotionProjectsFetcher
    from razd.ui.project_picker_dialog import ProjectSelection

_DURATION_OPTIONS = [30, 60, 90, 120]


class _FocusState:
    """Prosta maszyna stanów focus timera."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"

    def __init__(self) -> None:
        self.state = self.IDLE
        self.remaining_secs: int = 0
        self.total_secs: int = 0
        self.whitelist: set[str] = set()
        self.session_id: int | None = None
        self.started_at: str | None = None

    def start(self, minutes: int) -> None:
        self.remaining_secs = minutes * 60
        self.total_secs = self.remaining_secs
        self.state = self.RUNNING
        self.started_at = datetime.datetime.now().isoformat(timespec="seconds")

    def pause(self) -> None:
        if self.state == self.RUNNING:
            self.state = self.PAUSED

    def resume(self) -> None:
        if self.state == self.PAUSED:
            self.state = self.RUNNING

    def reset(self) -> None:
        self.state = self.IDLE
        self.remaining_secs = 0
        self.total_secs = 0
        self.session_id = None
        self.started_at = None

    def tick(self) -> bool:
        """Zwraca True jeśli timer skończył odliczanie."""
        if self.state == self.RUNNING and self.remaining_secs > 0:
            self.remaining_secs -= 1
            if self.remaining_secs == 0:
                self.state = self.IDLE
                return True
        return False


class _EscapeDialog(QDialog):
    """Dialog wyświetlany gdy user opuścił whitelistę w trakcie focus session."""

    def __init__(self, app_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAZD — uwaga!")
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        msg = QLabel(
            f"Opuściłeś focus session!\n\nAktywna aplikacja: <b>{app_name}</b>\n\n"
            "Wróć do dozwolonych aplikacji lub zatrzymaj timer."
        )
        msg.setTextFormat(Qt.RichText)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        buttons = QDialogButtonBox()
        self._btn_back = buttons.addButton("Wróć do focusa", QDialogButtonBox.AcceptRole)
        self._btn_stop = buttons.addButton("Zatrzymaj timer", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class _FocusSummaryDialog(QDialog):
    """Dialog podsumowania sesji focus z oceną i listą procesów."""

    def __init__(
        self,
        duration_s: int,
        score: int,
        process_counts: Counter[str],
        whitelist: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAZD — Podsumowanie sesji focus")
        self.setMinimumWidth(420)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # wynik
        score_color = "#2a6" if score >= 8 else ("#c80" if score >= 5 else "#c33")
        score_lbl = QLabel(f"<span style='font-size:52px;font-weight:bold;color:{score_color};'>{score}</span>"
                           f"<span style='font-size:20px;color:#888;'>/10</span>")
        score_lbl.setAlignment(Qt.AlignCenter)
        score_lbl.setTextFormat(Qt.RichText)
        layout.addWidget(score_lbl)

        bar = QProgressBar()
        bar.setRange(0, 10)
        bar.setValue(score)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {score_color}; border-radius: 4px; }}"
                          "QProgressBar { border-radius: 4px; background: #333; }")
        layout.addWidget(bar)

        # czas
        mm = duration_s // 60
        ss = duration_s % 60
        time_lbl = QLabel(f"Czas sesji: {mm}m {ss:02d}s")
        time_lbl.setAlignment(Qt.AlignCenter)
        time_lbl.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(time_lbl)

        # lista procesów
        if process_counts:
            proc_group = QGroupBox("Aktywne procesy podczas sesji")
            proc_layout = QVBoxLayout(proc_group)
            proc_list = QListWidget()
            proc_list.setMaximumHeight(160)
            total = sum(process_counts.values())
            wl_lower = {w.lower() for w in whitelist}
            for proc, count in process_counts.most_common(10):
                pct = round(count / total * 100)
                in_wl = any(w in proc.lower() for w in wl_lower)
                mark = "✓" if in_wl else "✗"
                color = "#5c5" if in_wl else "#c55"
                item = QListWidgetItem(f"{mark}  {proc}  —  {pct}%")
                from PySide6.QtGui import QColor
                item.setForeground(QColor(color))
                proc_list.addItem(item)
            proc_layout.addWidget(proc_list)
            layout.addWidget(proc_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


_FOCUS_BLOCK_COLOR = "#7C3AED"
_LABEL_COL_W = 50
_SLOT_H = 60

# ──────────────────────────────────────────────────────────────────────────────
# Tarcza zegarowa
# ──────────────────────────────────────────────────────────────────────────────

_DIAL_TRACK_COLOR   = QColor("#2a2a2a")
_DIAL_ARC_COLOR     = QColor("#7C3AED")
_DIAL_ARC_PAUSED    = QColor("#c80")
_DIAL_DOT_COLOR     = QColor("#a855f7")
_DIAL_TICK_MAJOR    = QColor("#555")
_DIAL_TICK_MINOR    = QColor("#2e2e2e")


class _ClockDial(QWidget):
    """Okrągła tarcza timera: podziałka, łuk postępu, krążek-wskaźnik, czas w środku."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._remaining_secs: int = 0
        self._total_secs: int = 0
        self._state: str = "idle"   # idle | running | paused
        self._subtitle: str = ""
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 200)

    def sizeHint(self) -> QSize:
        # kwadrat — dopasowuje się do dostępnej szerokości kolumny
        p = self.parentWidget()
        side = p.width() if p else 400
        return QSize(side, side)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return w

    def update_state(
        self,
        remaining_secs: int,
        total_secs: int,
        state: str,
        subtitle: str = "",
    ) -> None:
        self._remaining_secs = remaining_secs
        self._total_secs = total_secs
        self._state = state
        self._subtitle = subtitle
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QRect, QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        cx = self.width() / 2
        cy = self.height() / 2
        # grubość pierścienia skalowana proporcjonalnie
        track_w = max(10, int(side * 0.055))
        r_outer = side / 2 - 6
        r_track = r_outer - track_w / 2

        # ── 1. tło tarczy ────────────────────────────────────────────────
        face_r = r_outer - track_w - 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1a1a1a"))
        painter.drawEllipse(QRectF(cx - face_r, cy - face_r, face_r * 2, face_r * 2))

        # ── 2. podziałka (60 kresek) ──────────────────────────────────────
        tick_outer_r = r_outer - track_w - 4
        for i in range(60):
            angle_rad = math.radians(i * 6 - 90)
            is_major = (i % 5 == 0)
            tick_len = max(8, int(side * 0.035)) if is_major else max(4, int(side * 0.017))
            tick_inner_r = tick_outer_r - tick_len
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            painter.setPen(QPen(_DIAL_TICK_MAJOR if is_major else _DIAL_TICK_MINOR, 2 if is_major else 1))
            painter.drawLine(
                int(cx + cos_a * tick_inner_r), int(cy + sin_a * tick_inner_r),
                int(cx + cos_a * tick_outer_r), int(cy + sin_a * tick_outer_r),
            )

        # ── 3. pierścień ścieżki (szary) ─────────────────────────────────
        rect_track = QRectF(cx - r_track, cy - r_track, r_track * 2, r_track * 2)
        painter.setPen(QPen(_DIAL_TRACK_COLOR, track_w, Qt.SolidLine, Qt.FlatCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect_track)

        # ── 4. łuk postępu ────────────────────────────────────────────────
        progress = (self._total_secs - self._remaining_secs) / self._total_secs if self._total_secs > 0 else 0.0
        arc_color = _DIAL_ARC_PAUSED if self._state == "paused" else _DIAL_ARC_COLOR
        painter.setPen(QPen(arc_color, track_w, Qt.SolidLine, Qt.FlatCap))
        painter.drawArc(rect_track, 90 * 16, int(-progress * 360 * 16))

        # ── 5. krążek-wskaźnik ────────────────────────────────────────────
        if self._total_secs > 0:
            dot_angle = math.radians(progress * 360 - 90)
            dot_x = cx + math.cos(dot_angle) * r_track
            dot_y = cy + math.sin(dot_angle) * r_track
            dot_r = track_w / 2 + max(2, int(side * 0.012))
            painter.setPen(Qt.NoPen)
            painter.setBrush(_DIAL_DOT_COLOR)
            painter.drawEllipse(QRectF(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2))

        # ── 6. czas w środku ──────────────────────────────────────────────
        mm = self._remaining_secs // 60
        ss = self._remaining_secs % 60
        time_str = f"{mm:02d}:{ss:02d}"
        font_size = max(14, int(side * 0.15))
        font_time = QFont("Segoe UI", font_size, QFont.Weight.Bold)
        painter.setFont(font_time)
        painter.setPen(QPen(QColor("#ffffff")))
        inner_rect = QRect(int(cx - face_r), int(cy - face_r), int(face_r * 2), int(face_r * 2))
        # czas lekko powyżej środka gdy jest podtytuł
        offset_y = int(-face_r * 0.12) if self._subtitle else 0
        time_rect = QRect(inner_rect.x(), inner_rect.y() + offset_y,
                          inner_rect.width(), inner_rect.height())
        painter.drawText(time_rect, Qt.AlignHCenter | Qt.AlignVCenter, time_str)

        # ── 7. podtytuł ───────────────────────────────────────────────────
        if self._subtitle:
            font_sub = QFont("Segoe UI", max(9, int(side * 0.05)))
            painter.setFont(font_sub)
            painter.setPen(QPen(QColor("#888888")))
            sub_rect = QRect(
                int(cx - face_r),
                int(cy + face_r * 0.22),
                int(face_r * 2),
                int(face_r * 0.35),
            )
            painter.drawText(sub_rect, Qt.AlignHCenter | Qt.AlignTop, self._subtitle)

        painter.end()


_TL_VISIBLE_HOURS = 8   # ile godzin widocznych bez scrollowania


class _FocusVerticalCanvas(QWidget):
    """Pionowa oś czasu dla Focus Timera — skala 30-minutowa, góra=teraz."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sessions: list[tuple[str, str, str, int]] = []  # started_at, ended_at, proj_name, score
        self._now_ts: float = datetime.datetime.now().timestamp()
        # minimalna wysokość = 24h; szerokość od kontenera (setWidgetResizable=True)
        self.setMinimumHeight(_SLOT_H * 48)   # 24h × 2 sloty/h

    def set_sessions(self, sessions: list[tuple[str, str, str, int]]) -> None:
        self._sessions = sessions
        self.update()

    def add_session(self, started_at: str, ended_at: str, proj_name: str, score: int) -> None:
        self._sessions = self._sessions + [(started_at, ended_at, proj_name, score)]
        self.update()

    def tick(self) -> None:
        self._now_ts = datetime.datetime.now().timestamp()
        self.update()

    def _ts_to_y(self, ts: float) -> float:
        """Timestamp → Y (0=teraz, dół=przeszłość)."""
        elapsed_secs = self._now_ts - ts
        return elapsed_secs / 1800.0 * _SLOT_H

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = self.width()
        h = self.height()
        bx = _LABEL_COL_W
        bw = w - bx - 2

        # tło
        painter.fillRect(0, 0, w, h, QColor("#111111"))

        # oś etykiet
        painter.setPen(QPen(QColor("#333"), 1))
        painter.drawLine(bx - 1, 0, bx - 1, h)

        # linie 30-minutowe + etykiety — zawsze 48 slotów (24h)
        font_small = QFont("Segoe UI", 7)
        painter.setFont(font_small)
        now_dt = datetime.datetime.fromtimestamp(self._now_ts)

        for i in range(49):   # 0..48 = 24h * 2 sloty/h + 1
            y = int(i * _SLOT_H)
            line_ts = self._now_ts - i * 1800
            line_dt = datetime.datetime.fromtimestamp(line_ts)
            is_hour = line_dt.minute == 0

            painter.setPen(QPen(QColor("#333333" if is_hour else "#1e1e1e"), 1))
            painter.drawLine(bx, y, w, y)

            label = line_dt.strftime("%H:%M")
            painter.setPen(QPen(QColor("#888" if is_hour else "#444")))
            painter.drawText(0, y - 9, bx - 4, 18,
                             Qt.AlignRight | Qt.AlignVCenter, label)

        # bloki sesji focus
        for started_at, ended_at, proj_name, score in self._sessions:
            try:
                s_ts = datetime.datetime.fromisoformat(started_at).timestamp()
                e_ts = datetime.datetime.fromisoformat(ended_at).timestamp()
            except ValueError:
                continue
            y_top = self._ts_to_y(e_ts)
            y_bot = self._ts_to_y(s_ts)
            if y_bot < 0 or y_top > h:
                continue
            y_top = max(0.0, y_top)
            y_bot = min(float(h), y_bot)
            block_h = max(int(y_bot - y_top), 3)

            fill = QColor(_FOCUS_BLOCK_COLOR)
            fill.setAlpha(160)
            border = QColor(_FOCUS_BLOCK_COLOR)
            painter.fillRect(bx, int(y_top), bw, block_h, fill)
            painter.setPen(QPen(border, 1))
            painter.drawRect(bx, int(y_top), bw, block_h)

            # pasek u góry bloku
            painter.fillRect(bx, int(y_top), bw, 4, border)

            # etykieta projektu i wyniku
            if block_h >= 20:
                font_lbl = QFont("Segoe UI", 7)
                painter.setFont(font_lbl)
                painter.setPen(QPen(QColor("#ffffff")))
                dur_m = round((e_ts - s_ts) / 60)
                line1 = proj_name[:22] if proj_name else f"{dur_m}m"
                line2 = f"{dur_m}m · {score}/10" if proj_name else f"wynik {score}/10"
                painter.drawText(bx + 4, int(y_top) + 5, bw - 6, 14,
                                 Qt.AlignLeft | Qt.AlignVCenter, line1)
                if block_h >= 36:
                    painter.drawText(bx + 4, int(y_top) + 19, bw - 6, 14,
                                     Qt.AlignLeft | Qt.AlignVCenter, line2)

        # linia "Teraz" — na górze
        painter.setPen(QPen(QColor("#FF5252"), 2))
        painter.drawLine(bx, 1, w, 1)
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#FF5252")))
        painter.drawText(0, 0, bx - 4, 18, Qt.AlignRight | Qt.AlignVCenter,
                         now_dt.strftime("%H:%M"))

        painter.end()


class RazdFocusTimerTab(QWidget):
    """Zakładka Focus Timer — whitelist appek, timer 30-120min, alerty."""

    # emitowany gdy app spoza whitelisty (nazwa procesu)
    focus_escaped = Signal(str)
    # emitowany po zakończeniu sesji: started_at, ended_at, duration_s, score
    focus_session_ended = Signal(str, str, int, int)

    def __init__(
        self,
        repo: RazdRepository | None = None,
        fetcher: NotionProjectsFetcher | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._fetcher = fetcher
        self._state = _FocusState()
        self._tray: QSystemTrayIcon | None = None
        self._escape_dialog_open = False
        self._active_project: ProjectSelection | None = None

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._on_tick)

        self._build_ui()
        self._setup_tray()
        self._update_ui()
        self._load_today_sessions()

    # -----------------------------------------------------------------
    # Budowa UI
    # -----------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        # ── lewa kolumna: kompaktowa whitelist ────────────────────────────
        wl_widget = QWidget()
        wl_widget.setMaximumWidth(180)
        wl_layout = QVBoxLayout(wl_widget)
        wl_layout.setContentsMargins(4, 4, 4, 4)
        wl_layout.setSpacing(4)

        wl_lbl = QLabel("Whitelist")
        wl_lbl.setStyleSheet("color: #666; font-size: 10px; font-weight: bold;")
        wl_layout.addWidget(wl_lbl)

        self._wl_list = QListWidget()
        self._wl_list.setToolTip("Aplikacje dozwolone w trakcie focus session")
        self._wl_list.setMaximumHeight(110)
        self._wl_list.setStyleSheet("font-size: 10px;")
        wl_layout.addWidget(self._wl_list)

        wl_btn_row = QHBoxLayout()
        wl_btn_row.setSpacing(3)
        btn_add = QPushButton("+")
        btn_add.setFixedSize(28, 22)
        btn_add.setToolTip("Dodaj do whitelisty")
        btn_add.clicked.connect(self._add_to_whitelist)
        btn_remove = QPushButton("−")
        btn_remove.setFixedSize(28, 22)
        btn_remove.setToolTip("Usuń z whitelisty")
        btn_remove.clicked.connect(self._remove_from_whitelist)
        wl_btn_row.addWidget(btn_add)
        wl_btn_row.addWidget(btn_remove)
        wl_btn_row.addStretch()
        wl_layout.addLayout(wl_btn_row)
        wl_layout.addStretch()

        splitter.addWidget(wl_widget)

        # ── środkowa kolumna: tarcza + kontrolki ──────────────────────────
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(8)

        # tarcza zegarowa — zajmuje całą dostępną przestrzeń pionową
        self._dial = _ClockDial()
        center_layout.addWidget(self._dial, 1)

        # projekt label
        self._project_label = QLabel("Projekt: brak")
        self._project_label.setAlignment(Qt.AlignCenter)
        self._project_label.setStyleSheet(
            "color: #888; font-size: 11px; padding: 3px 8px;"
            " border: 1px solid #333; border-radius: 4px;"
        )
        self._project_label.setWordWrap(True)
        center_layout.addWidget(self._project_label)

        # presety + spinbox w jednym rzędzie
        dur_row = QHBoxLayout()
        dur_row.setSpacing(4)
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(1, 180)
        self._duration_spin.setValue(60)
        self._duration_spin.setSingleStep(5)
        self._duration_spin.setFixedWidth(60)
        self._duration_spin.setStyleSheet("font-size: 11px;")
        dur_row.addWidget(self._duration_spin)
        dur_row.addWidget(QLabel("min"))
        dur_row.addStretch()
        for mins in _DURATION_OPTIONS:
            btn = QPushButton(f"{mins}m")
            btn.setFixedSize(38, 24)
            btn.setStyleSheet("font-size: 10px; padding: 0;")
            btn.clicked.connect(lambda checked=False, m=mins: self._set_duration(m))
            dur_row.addWidget(btn)
        center_layout.addLayout(dur_row)

        # przyciski Start / Reset
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)
        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setStyleSheet(
            "background: #2a6; color: white; font-weight: bold;"
            " padding: 8px 24px; font-size: 13px; border-radius: 6px;"
        )
        self._btn_start.clicked.connect(self._on_start_pause)
        self._btn_reset = QPushButton("■  Reset")
        self._btn_reset.setStyleSheet(
            "background: #444; color: #ccc; padding: 8px 16px;"
            " font-size: 12px; border-radius: 6px;"
        )
        self._btn_reset.clicked.connect(self._on_reset)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._btn_start)
        ctrl_row.addWidget(self._btn_reset)
        ctrl_row.addStretch()
        center_layout.addLayout(ctrl_row)

        # status
        self._status_label = QLabel("Gotowy")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #666; font-size: 10px;")
        center_layout.addWidget(self._status_label)

        # ukryty time_display — kompatybilność z _update_ui
        self._time_display = QLabel()
        self._time_display.hide()

        splitter.addWidget(center)

        # ── prawa kolumna: pionowa oś czasu sesji ─────────────────────────
        tl_box = QGroupBox("Timeline")
        tl_layout = QVBoxLayout(tl_box)
        tl_layout.setContentsMargins(4, 4, 4, 4)

        self._focus_canvas = _FocusVerticalCanvas()
        scroll = QScrollArea()
        scroll.setWidget(self._focus_canvas)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: #111; }")
        self._tl_scroll = scroll
        tl_layout.addWidget(scroll)

        splitter.addWidget(tl_box)
        splitter.setSizes([160, 400, 220])

        root.addWidget(splitter)

        # ticker canvasu co minutę
        self._canvas_tick = QTimer(self)
        self._canvas_tick.setInterval(60_000)
        self._canvas_tick.timeout.connect(self._focus_canvas.tick)
        self._canvas_tick.start()

    def _load_today_sessions(self) -> None:
        """Ładuje dzisiejsze sesje focus do canvas przy starcie."""
        if not self._repo:
            return
        today = datetime.date.today().isoformat()
        sessions = []
        for fs in self._repo.get_focus_sessions_for_day(today):
            if not fs.ended_at or fs.score is None:
                continue
            proj_name = ""
            fsp = self._repo.get_session_project(fs.id)
            if fsp:
                if fsp.custom_project_name:
                    proj_name = fsp.custom_project_name
                elif fsp.notion_project_id:
                    np_row = self._repo.get_notion_project_by_id(fsp.notion_project_id)
                    if np_row:
                        proj_name = np_row.name
            sessions.append((fs.started_at, fs.ended_at, proj_name, fs.score))
        self._focus_canvas.set_sessions(sessions)

    def _setup_tray(self) -> None:
        try:
            self._tray = QSystemTrayIcon(self)
            self._tray.setToolTip("RAZD Focus Timer")
        except Exception:
            self._tray = None

    # -----------------------------------------------------------------
    # Logika timera
    # -----------------------------------------------------------------

    def _on_start_pause(self) -> None:
        if self._state.state == _FocusState.IDLE:
            selection = self._pick_project()
            if selection is None:
                return  # user anulował dialog
            self._active_project = selection
            self._state.start(self._duration_spin.value())
            if self._repo:
                self._state.session_id = self._repo.start_focus_session(
                    self._state.started_at,  # type: ignore[arg-type]
                    self._state.whitelist,
                )
                self._save_project_link()
            self._ticker.start()
        elif self._state.state == _FocusState.RUNNING:
            self._state.pause()
        elif self._state.state == _FocusState.PAUSED:
            self._state.resume()
        self._update_ui()

    def _pick_project(self) -> ProjectSelection | None:
        from razd.ui.project_picker_dialog import ProjectPickerDialog
        dlg = ProjectPickerDialog(fetcher=self._fetcher, repo=self._repo, parent=self)
        if dlg.exec() == QDialog.Accepted:
            return dlg.selection()
        return None

    def _save_project_link(self) -> None:
        if not self._repo or not self._state.session_id or not self._active_project:
            return
        sel = self._active_project
        notion_id: int | None = None
        custom_name: str | None = None
        if sel.is_custom:
            custom_name = sel.custom_name
        elif sel.notion_project:
            row = self._repo.get_notion_project_by_page_id(sel.notion_project.notion_page_id)
            notion_id = row.id if row else None
        self._repo.link_focus_session_project(
            self._state.session_id, notion_id, custom_name
        )

    def _on_reset(self) -> None:
        self._ticker.stop()
        if self._state.state != _FocusState.IDLE and self._state.session_id and self._repo:
            elapsed = self._state.total_secs - self._state.remaining_secs
            score, _ = self._compute_score()
            self._repo.end_focus_session(
                self._state.session_id,
                datetime.datetime.now().isoformat(timespec="seconds"),
                elapsed,
                score,
            )
        self._active_project = None
        self._state.reset()
        self._update_ui()

    def _set_duration(self, mins: int) -> None:
        if self._state.state == _FocusState.IDLE:
            self._duration_spin.setValue(mins)

    def _on_tick(self) -> None:
        finished = self._state.tick()
        self._update_ui()
        if finished:
            self._ticker.stop()
            self._on_timer_done()

    def _on_timer_done(self) -> None:
        now_str = datetime.datetime.now().isoformat(timespec="seconds")
        duration_s = self._state.total_secs
        score, process_counts = self._compute_score()

        if self._repo and self._state.session_id:
            self._repo.end_focus_session(self._state.session_id, now_str, duration_s, score)

        started_at = self._state.started_at or now_str
        session_id = self._state.session_id
        project = self._active_project
        self._active_project = None
        self._state.reset()

        proj_name = ""
        if project and not project.is_custom and project.notion_project:
            proj_name = project.notion_project.name
        elif project and project.is_custom and project.custom_name:
            proj_name = project.custom_name

        self._status_label.setText(f"Session zakończona o {datetime.datetime.now().strftime('%H:%M')}!")
        self._notify_tray("RAZD", f"Focus session zakończona! Wynik: {score}/10")
        self._play_finish_sound()

        # dodaj sesję na lokalny canvas
        self._focus_canvas.add_session(started_at, now_str, proj_name, score)

        self.focus_session_ended.emit(started_at, now_str, duration_s, score)

        # sync czasu do Notion w tle
        if project and not project.is_custom and project.notion_project and self._repo and session_id:
            self._sync_time_to_notion(project, duration_s, session_id)

        dlg = _FocusSummaryDialog(duration_s, score, process_counts, self._state.whitelist, self)
        dlg.exec()

    def _sync_time_to_notion(
        self,
        project: ProjectSelection,
        duration_s: int,
        session_id: int,
    ) -> None:
        from razd.notion.projects_fetcher import write_session_time_to_notion
        duration_mins = max(1, round(duration_s / 60))
        np = project.notion_project
        if np is None:
            return
        ok = write_session_time_to_notion(np, duration_mins)
        if ok and self._repo:
            self._repo.mark_session_project_synced(session_id)

    # -----------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------

    def _compute_score(self) -> tuple[int, Counter[str]]:
        if not self._repo or not self._state.session_id:
            return 1, Counter()
        samples = self._repo.get_focus_process_samples(self._state.session_id)
        if not samples:
            return 1, Counter()
        process_counts: Counter[str] = Counter(proc for _, proc in samples)
        wl_lower = {w.lower() for w in self._state.whitelist}
        if not wl_lower:
            return 10, process_counts  # brak whitelisty = brak oceny, dajemy max
        whitelist_count = sum(
            count
            for proc, count in process_counts.items()
            if any(w in proc.lower() for w in wl_lower)
        )
        score = max(1, min(10, round(whitelist_count / len(samples) * 10)))
        return score, process_counts

    # -----------------------------------------------------------------
    # Sprawdzanie whitelisty — wołane z zewnątrz przez main_window
    # -----------------------------------------------------------------

    def check_active_app(self, process_name: str) -> None:
        """Wołane przy każdym evencie trackera gdy focus session aktywna."""
        if self._state.state != _FocusState.RUNNING:
            return

        # zapisz próbkę procesu do DB (niezależnie od whitelist membership)
        if self._repo and self._state.session_id:
            self._repo.add_focus_process_sample(
                self._state.session_id,
                datetime.datetime.now().isoformat(timespec="seconds"),
                process_name,
            )

        if not self._state.whitelist:
            return
        proc_lower = process_name.lower()
        for allowed in self._state.whitelist:
            if allowed.lower() in proc_lower:
                return
        # poza whitelistą — alert
        if not self._escape_dialog_open:
            self._trigger_escape_alert(process_name)

    def _trigger_escape_alert(self, app_name: str) -> None:
        self._escape_dialog_open = True
        self._notify_tray("RAZD — uwaga!", f"Opuściłeś focus session! Aktywna: {app_name}")
        dlg = _EscapeDialog(app_name, self)
        result = dlg.exec()
        self._escape_dialog_open = False
        if result == QDialog.Rejected:
            self._on_reset()

    def _notify_tray(self, title: str, message: str) -> None:
        if self._tray and QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)

    def _play_finish_sound(self) -> None:
        """Odtwarza dźwięk zakończenia sesji w osobnym wątku (nie blokuje UI)."""
        def _play() -> None:
            try:
                import winsound
                for _ in range(3):
                    winsound.Beep(880, 200)
                    winsound.Beep(1100, 300)
            except Exception:
                pass
        threading.Thread(target=_play, daemon=True).start()

    # -----------------------------------------------------------------
    # Whitelist
    # -----------------------------------------------------------------

    def _add_to_whitelist(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Dodaj do whitelisty", "Nazwa procesu (np. python.exe, chrome.exe):"
        )
        if ok and text.strip():
            name = text.strip()
            self._state.whitelist.add(name)
            self._wl_list.addItem(QListWidgetItem(name))

    def _remove_from_whitelist(self) -> None:
        row = self._wl_list.currentRow()
        if row < 0:
            return
        item = self._wl_list.takeItem(row)
        if item:
            self._state.whitelist.discard(item.text())

    # -----------------------------------------------------------------
    # Aktualizacja UI
    # -----------------------------------------------------------------

    def _update_ui(self) -> None:
        s = self._state.state

        # subtitle tarczy
        if s == _FocusState.IDLE:
            subtitle = ""
        elif s == _FocusState.RUNNING:
            subtitle = "focus"
        else:
            subtitle = "pauza"

        self._dial.update_state(
            self._state.remaining_secs,
            self._state.total_secs,
            s,
            subtitle,
        )

        if s == _FocusState.IDLE:
            self._btn_start.setText("▶  Start")
            self._btn_start.setStyleSheet(
                "background: #2a6; color: white; font-weight: bold;"
                " padding: 8px 24px; font-size: 13px; border-radius: 6px;"
            )
            self._status_label.setText("Gotowy")
            self._duration_spin.setEnabled(True)
            self._project_label.setText("Projekt: brak")
            self._project_label.setStyleSheet(
                "color: #555; font-size: 11px; padding: 3px 8px;"
                " border: 1px solid #333; border-radius: 4px;"
            )
        elif s == _FocusState.RUNNING:
            self._btn_start.setText("⏸  Pauza")
            self._btn_start.setStyleSheet(
                "background: #c80; color: white; font-weight: bold;"
                " padding: 8px 24px; font-size: 13px; border-radius: 6px;"
            )
            self._status_label.setText("Session aktywna")
            self._duration_spin.setEnabled(False)
            self._refresh_project_label()
        elif s == _FocusState.PAUSED:
            self._btn_start.setText("▶  Wznów")
            self._btn_start.setStyleSheet(
                "background: #2a6; color: white; font-weight: bold;"
                " padding: 8px 24px; font-size: 13px; border-radius: 6px;"
            )
            self._status_label.setText("Wstrzymany")
            self._duration_spin.setEnabled(False)
            self._refresh_project_label()

    def _refresh_project_label(self) -> None:
        if self._active_project:
            name = self._active_project.display_name()
            color = "#888" if self._active_project.is_custom else "#4A90D9"
            border = "#444" if self._active_project.is_custom else "#2a4a6a"
        else:
            name = "Projekt: brak"
            color = "#555"
            border = "#333"
        self._project_label.setText(f"Projekt: {name}")
        self._project_label.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 4px 8px;"
            f" border: 1px solid {border}; border-radius: 4px;"
        )
