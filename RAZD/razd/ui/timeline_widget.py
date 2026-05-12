from __future__ import annotations

import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolTip, QVBoxLayout, QWidget

from razd.tracker.activity_classifier import (
    ACTIVITY_ALPHA,
    ACTIVITY_COLORS,
    ActivityBlock,
    ActivityType,
)

_LABEL_W = 50   # px — szerokość kolumny z etykietami godzin
_SCALE_OPTIONS: list[tuple[str, int]] = [
    ("3h", 3),
    ("6h", 6),
    ("12h", 12),
    ("24h", 24),
    ("72h", 72),
]

_DAYS_PL = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]


def _day_short(dt: datetime.datetime) -> str:
    return _DAYS_PL[dt.weekday()]


class _TimelineCanvas(QWidget):
    """
    Pionowe płótno osi czasu.
    Góra = teraz, dół = okno_skali godzin temu.
    Zawsze rysuje poziome linie co 1h.
    Na skali 72h — wyraźne separatory dób.
    Hover → tooltip z dokładną godziną.
    """

    scale_step_requested = Signal(int)  # +1 lub -1 (scroll wheel)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._blocks: list[ActivityBlock] = []
        self._scale_h: int = 6
        self._now_ts: float = datetime.datetime.now().timestamp()
        self.setMinimumWidth(100)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_blocks(self, blocks: list[ActivityBlock]) -> None:
        self._blocks = blocks
        self.update()

    def set_scale(self, hours: int) -> None:
        self._scale_h = hours
        self.update()

    def tick(self) -> None:
        self._now_ts = datetime.datetime.now().timestamp()
        self.update()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _ts_to_y(self, ts: float) -> float:
        """Timestamp → Y (0=teraz, height=najstarszy)."""
        frac = (self._now_ts - ts) / (self._scale_h * 3600)
        return max(0.0, min(frac * self.height(), float(self.height())))

    def _y_to_ts(self, y: float) -> float:
        """Y → timestamp."""
        frac = y / max(self.height(), 1)
        return self._now_ts - frac * (self._scale_h * 3600)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w = self.width()
        h = self.height()
        oldest_ts = self._now_ts - self._scale_h * 3600
        bx = _LABEL_W      # bloki zaczynają się tutaj
        bw = w - bx - 2

        # ── 1. tło ──────────────────────────────────────────────────────
        painter.fillRect(0, 0, w, h, QColor("#111111"))

        # ── 2. bloki aktywności ─────────────────────────────────────────
        for block in self._blocks:
            bs = max(block.start_ts, oldest_ts)
            be = min(block.end_ts, self._now_ts)
            if be <= bs:
                continue
            y_top = int(self._ts_to_y(be))
            y_bot = int(self._ts_to_y(bs))
            rect_h = max(y_bot - y_top, 1)
            color = QColor(ACTIVITY_COLORS[block.activity])
            color.setAlpha(ACTIVITY_ALPHA[block.activity])
            painter.fillRect(bx, y_top, bw, rect_h, color)

        # ── 3. linia separatora etykiet ─────────────────────────────────
        painter.setPen(QPen(QColor("#333"), 1))
        painter.drawLine(_LABEL_W - 1, 0, _LABEL_W - 1, h)

        # ── 4. linie godzinne + etykiety ────────────────────────────────
        self._draw_grid(painter, w, h, bx, bw, oldest_ts)

        # ── 5. "Teraz" ──────────────────────────────────────────────────
        now_dt = datetime.datetime.fromtimestamp(self._now_ts)
        painter.setPen(QPen(QColor("#FF5252"), 2))
        painter.drawLine(bx, 1, w, 1)
        font_now = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(font_now)
        painter.setPen(QPen(QColor("#FF5252")))
        painter.drawText(0, 0, _LABEL_W - 3, 18,
                         Qt.AlignRight | Qt.AlignVCenter,
                         now_dt.strftime("%H:%M"))

        painter.end()

    def _draw_grid(
        self,
        painter: QPainter,
        w: int,
        h: int,
        bx: int,
        bw: int,
        oldest_ts: float,
    ) -> None:
        """Rysuje linie siatki i etykiety. Zawsze co 1h linia; etykiety zależą od skali."""
        now_dt = datetime.datetime.fromtimestamp(self._now_ts)
        oldest_dt = datetime.datetime.fromtimestamp(oldest_ts)

        # zaokrągl w dół do pełnej godziny
        cursor = oldest_dt.replace(minute=0, second=0, microsecond=0)
        if cursor < oldest_dt:
            cursor += datetime.timedelta(hours=1)

        label_step_h = self._label_step_h()
        font_small = QFont("Segoe UI", 7)
        font_day = QFont("Segoe UI", 8, QFont.Weight.Bold)

        while cursor <= now_dt + datetime.timedelta(hours=1):
            ts = cursor.timestamp()
            y = int(self._ts_to_y(ts))

            if -2 <= y <= h + 2:
                is_midnight = cursor.hour == 0

                if is_midnight and self._scale_h > 24:
                    # ── separator doby na 72h ──
                    # linia przez całą szerokość (w tym etykiety)
                    painter.setPen(QPen(QColor("#4A7FA0"), 2))
                    painter.drawLine(0, y, w, y)

                    # tło band-badge z datą
                    badge_text = f"{_day_short(cursor)} {cursor.strftime('%d.%m')}"
                    painter.setFont(font_day)
                    painter.setPen(QPen(QColor("#7BBFE0")))
                    painter.drawText(0, y + 2, _LABEL_W - 3, 16,
                                     Qt.AlignRight | Qt.AlignVCenter, badge_text)
                    painter.setFont(font_small)

                elif is_midnight:
                    # separator doby na 24h i mniejszych
                    painter.setPen(QPen(QColor("#555"), 1))
                    painter.drawLine(bx, y, w, y)
                    painter.setFont(font_small)
                    painter.setPen(QPen(QColor("#999")))
                    painter.drawText(0, y - 9, _LABEL_W - 4, 18,
                                     Qt.AlignRight | Qt.AlignVCenter,
                                     cursor.strftime("%d.%m"))
                else:
                    # zwykła linia godzinowa
                    painter.setPen(QPen(QColor("#232323"), 1))
                    painter.drawLine(bx, y, w, y)

                    # etykieta tylko co label_step_h godzin
                    if label_step_h > 0 and cursor.hour % label_step_h == 0:
                        painter.setFont(font_small)
                        painter.setPen(QPen(QColor("#666")))
                        painter.drawText(0, y - 9, _LABEL_W - 4, 18,
                                         Qt.AlignRight | Qt.AlignVCenter,
                                         cursor.strftime("%H:%M"))

            cursor += datetime.timedelta(hours=1)

    def _label_step_h(self) -> int:
        """Co ile godzin wyświetlać etykietę (0 = brak etykiet godzinowych)."""
        if self._scale_h <= 3:
            return 1
        if self._scale_h <= 6:
            return 2
        if self._scale_h <= 12:
            return 3
        if self._scale_h <= 24:
            return 6
        return 0  # 72h: tylko separatory dób, bez etykiet godzin

    # ------------------------------------------------------------------
    # Tooltip na hover
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        ts = self._y_to_ts(event.position().y())
        dt = datetime.datetime.fromtimestamp(ts)
        day = _DAYS_PL[dt.weekday()]
        tip = f"{day} {dt.strftime('%d.%m.%Y  %H:%M')}"
        QToolTip.showText(event.globalPosition().toPoint(), tip)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        QToolTip.hideText()
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale_step_requested.emit(-1)  # przybliżenie = mniejszy zakres
        elif delta < 0:
            self.scale_step_requested.emit(1)   # oddalenie = większy zakres
        event.accept()


class RazdVerticalTimeline(QWidget):
    """Pionowa oś czasu z wyborem skali (3h/6h/12h/24h/72h)."""

    scale_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = _TimelineCanvas()
        self._scale_btns: dict[int, QPushButton] = {}
        self._current_scale = 6
        self._build_ui()

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._canvas.tick)
        self._tick.start(60_000)

    @property
    def current_scale(self) -> int:
        return self._current_scale

    def set_blocks(self, blocks: list[ActivityBlock]) -> None:
        self._canvas.set_blocks(blocks)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 4, 0)
        root.setSpacing(3)

        # Przyciski skali
        btn_row = QHBoxLayout()
        btn_row.setSpacing(2)
        btn_row.setContentsMargins(0, 0, 0, 0)
        for lbl, hours in _SCALE_OPTIONS:
            btn = QPushButton(lbl)
            btn.setFixedHeight(20)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton {"
                "  font-size: 9px; padding: 0 3px;"
                "  border: 1px solid #444; border-radius: 3px;"
                "  background: #2a2a2a; color: #888;"
                "}"
                "QPushButton:checked {"
                "  background: #1565C0; color: #fff; border-color: #1976D2;"
                "}"
                "QPushButton:hover { border-color: #666; }"
            )
            btn.clicked.connect(lambda _=False, h=hours: self._on_scale(h))
            self._scale_btns[hours] = btn
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        root.addWidget(self._canvas, 1)

        self._canvas.scale_step_requested.connect(self._on_wheel_step)
        self._apply_scale(6)

    def _on_scale(self, hours: int) -> None:
        self._apply_scale(hours)
        self.scale_changed.emit(hours)

    def _on_wheel_step(self, direction: int) -> None:
        """direction: -1 = przybliż (mniejszy zakres), +1 = oddal (większy zakres)."""
        scales = [h for _, h in _SCALE_OPTIONS]
        try:
            idx = scales.index(self._current_scale)
        except ValueError:
            idx = 1  # fallback do 6h
        new_idx = max(0, min(len(scales) - 1, idx + direction))
        if new_idx != idx:
            self._apply_scale(scales[new_idx])
            self.scale_changed.emit(scales[new_idx])

    def _apply_scale(self, hours: int) -> None:
        self._current_scale = hours
        for h, btn in self._scale_btns.items():
            btn.setChecked(h == hours)
        self._canvas.set_scale(hours)
