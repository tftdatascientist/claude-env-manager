from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QSplitter, QVBoxLayout, QWidget

from razd.tracker.activity_classifier import (
    ACTIVITY_ALPHA,
    ACTIVITY_COLORS,
    ActivityBlock,
    ActivityType,
    classify_events,
    fill_gaps,
)
from razd.ui.stats_widget import RazdMonthlyStatsWidget, RazdWeeklyStatsWidget
from razd.ui.timeline_widget import RazdVerticalTimeline

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository


class RazdTimelineTab(QWidget):
    """Osobna zakładka Timeline — pionowa oś czasu z pełnym pokryciem doby."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._weekly_stats: RazdWeeklyStatsWidget | None = None
        self._monthly_stats: RazdMonthlyStatsWidget | None = None
        self._build_ui()

        # Odświeżaj co 60s (nie za często — DB query)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(60_000)

        self._refresh()

    # ------------------------------------------------------------------

    def set_repo(self, repo: RazdRepository) -> None:
        self._repo = repo
        if self._weekly_stats is not None:
            self._weekly_stats.set_repo(repo)
        if self._monthly_stats is not None:
            self._monthly_stats.set_repo(repo)
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
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        layout = QVBoxLayout(inner)
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

        layout.addSpacing(8)

        def _sep() -> QLabel:
            s = QLabel()
            s.setFixedHeight(1)
            s.setStyleSheet("background: #333;")
            return s

        # --- Statystyki tygodnia ---
        layout.addWidget(_sep())
        stats_week_title = QLabel("Statystyki tygodnia")
        stats_week_title.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        layout.addWidget(stats_week_title)
        self._weekly_stats = RazdWeeklyStatsWidget(self._repo)
        layout.addWidget(self._weekly_stats)

        layout.addSpacing(4)

        # --- Statystyki miesiąca ---
        layout.addWidget(_sep())
        stats_month_title = QLabel("Statystyki miesiąca (30 dni)")
        stats_month_title.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        layout.addWidget(stats_month_title)
        self._monthly_stats = RazdMonthlyStatsWidget(self._repo)
        layout.addWidget(self._monthly_stats)

        layout.addStretch()

        scroll.setWidget(inner)
        outer_layout.addWidget(scroll, 1)

        # Last refresh info — poza scroll area (zawsze widoczne)
        self._last_refresh_lbl = QLabel("—")
        self._last_refresh_lbl.setStyleSheet("color: #555; font-size: 9px; padding: 2px 12px;")
        outer_layout.addWidget(self._last_refresh_lbl)

        return outer

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
