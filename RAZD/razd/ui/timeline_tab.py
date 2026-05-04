from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from razd.tracker.activity_classifier import (
    ACTIVITY_ALPHA,
    ACTIVITY_COLORS,
    ActivityBlock,
    ActivityType,
    classify_events,
    fill_gaps,
)
from razd.ui.timeline_widget import RazdVerticalTimeline

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository


class RazdTimelineTab(QWidget):
    """Osobna zakładka Timeline — pionowa oś czasu z pełnym pokryciem doby."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._build_ui()

        # Odświeżaj co 60s (nie za często — DB query)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(60_000)

        self._refresh()

    # ------------------------------------------------------------------

    def set_repo(self, repo: RazdRepository) -> None:
        self._repo = repo
        self._refresh()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # --- Left: the timeline itself (takes most of the width) ---
        self._tl = RazdVerticalTimeline()
        self._tl.scale_changed.connect(self._refresh)
        splitter.addWidget(self._tl)

        # --- Right: info sidebar ---
        sidebar = self._build_sidebar()
        splitter.addWidget(sidebar)

        # Timeline gets most space, sidebar gets the rest
        splitter.setSizes([320, 220])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Timeline")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ddd;")
        layout.addWidget(title)

        desc = QLabel(
            "Pionowa oś czasu — cała wybrana doba podzielona na kategorie aktywności."
            " Szary = komputer wyłączony."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(desc)

        layout.addSpacing(8)

        # Legend
        legend_title = QLabel("Kategorie:")
        legend_title.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        layout.addWidget(legend_title)

        descriptions = {
            ActivityType.DEEP_FOCUS: "Timer aktywny, brak YT/sociali",
            ActivityType.FOCUS: "Timer aktywny, YT lub sociale",
            ActivityType.WORK: "Praca — bez timera",
            ActivityType.CHILL: "YT/sociale, spokojne tempo",
            ActivityType.AWAY: "Komputer włączony, brak aktywności 5+ min",
            ActivityType.OFF: "Komputer wyłączony",
        }

        for activity, color in ACTIVITY_COLORS.items():
            row = QHBoxLayout()
            dot = QLabel("■")
            dot.setFixedWidth(16)
            dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            text_col = QVBoxLayout()
            name_lbl = QLabel(activity.value)
            name_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
            desc_lbl = QLabel(descriptions[activity])
            desc_lbl.setStyleSheet("color: #666; font-size: 9px;")
            desc_lbl.setWordWrap(True)
            text_col.addWidget(name_lbl)
            text_col.addWidget(desc_lbl)
            row.addWidget(dot, 0, Qt.AlignTop)
            row.addLayout(text_col, 1)
            layout.addLayout(row)

        layout.addStretch()

        # Last refresh info
        self._last_refresh_lbl = QLabel("—")
        self._last_refresh_lbl.setStyleSheet("color: #555; font-size: 9px;")
        layout.addWidget(self._last_refresh_lbl)

        return w

    # ------------------------------------------------------------------

    def _refresh(self, _scale: int | None = None) -> None:
        if self._repo is None:
            return

        now_ts = datetime.datetime.now().timestamp()
        scale_h = self._tl.current_scale
        oldest_ts = now_ts - scale_h * 3600

        events = self._repo.get_events_for_range(oldest_ts, now_ts)
        focus_sessions = self._repo.get_focus_sessions_for_range(oldest_ts, now_ts)

        raw_blocks = classify_events(events, focus_sessions, now_ts)
        full_blocks = fill_gaps(raw_blocks, oldest_ts, now_ts)

        self._tl.set_blocks(full_blocks)

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self._last_refresh_lbl.setText(f"Ostatnie odświeżenie: {now_str}")
