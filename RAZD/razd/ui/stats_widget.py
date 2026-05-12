from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository

_DAYS_PL = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]


def _fmt_hm(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"


def _make_bar(color: str) -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setFixedHeight(8)
    bar.setTextVisible(False)
    bar.setStyleSheet(
        f"QProgressBar {{ background: #2a2a2a; border: none; border-radius: 3px; }}"
        f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
    )
    return bar


class RazdWeeklyStatsWidget(QWidget):
    """Ostatnie 7 dni — paski PC ON / Praca / Idle."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(3)
        self._bars: list[tuple[QProgressBar, QProgressBar, QProgressBar]] = []
        self._val_labels: list[tuple[QLabel, QLabel, QLabel]] = []
        self._build_rows()
        if repo is not None:
            self.refresh()

    def set_repo(self, repo: RazdRepository) -> None:
        self._repo = repo
        self.refresh()

    def _build_rows(self) -> None:
        headers = ["Dzień", "Data", "PC ON", "", "Praca", "", "Idle", ""]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet("color: #666; font-size: 8px;")
            self._grid.addWidget(lbl, 0, col)

        for row in range(1, 8):
            day_lbl = QLabel("—")
            day_lbl.setStyleSheet("color: #aaa; font-size: 9px; font-weight: bold;")
            date_lbl = QLabel("—")
            date_lbl.setStyleSheet("color: #666; font-size: 8px;")

            bar_pc = _make_bar("#4A90D9")
            val_pc = QLabel("—")
            val_pc.setStyleSheet("color: #4A90D9; font-size: 8px;")
            val_pc.setMinimumWidth(40)

            bar_work = _make_bar("#2a6")
            val_work = QLabel("—")
            val_work.setStyleSheet("color: #2a6; font-size: 8px;")
            val_work.setMinimumWidth(40)

            bar_idle = _make_bar("#666")
            val_idle = QLabel("—")
            val_idle.setStyleSheet("color: #888; font-size: 8px;")
            val_idle.setMinimumWidth(40)

            self._grid.addWidget(day_lbl, row, 0)
            self._grid.addWidget(date_lbl, row, 1)
            self._grid.addWidget(bar_pc, row, 2)
            self._grid.addWidget(val_pc, row, 3)
            self._grid.addWidget(bar_work, row, 4)
            self._grid.addWidget(val_work, row, 5)
            self._grid.addWidget(bar_idle, row, 6)
            self._grid.addWidget(val_idle, row, 7)

            self._bars.append((bar_pc, bar_work, bar_idle))
            self._val_labels.append((val_pc, val_work, val_idle))

        self._day_labels: list[QLabel] = []
        self._date_labels: list[QLabel] = []
        for row in range(1, 8):
            self._day_labels.append(self._grid.itemAtPosition(row, 0).widget())  # type: ignore[union-attr]
            self._date_labels.append(self._grid.itemAtPosition(row, 1).widget())  # type: ignore[union-attr]

    def refresh(self) -> None:
        if self._repo is None:
            return

        today = datetime.date.today()
        stats_list = []
        for delta in range(6, -1, -1):  # od 6 dni temu do dziś (0)
            d = today - datetime.timedelta(days=delta)
            stats_list.append(self._repo.compute_day_stats(d.isoformat()))

        max_uptime = max((s.uptime_s for s in stats_list), default=1) or 1

        for i, stats in enumerate(stats_list):
            d = datetime.date.fromisoformat(stats.date)
            self._day_labels[i].setText(_DAYS_PL[d.weekday()])
            self._date_labels[i].setText(d.strftime("%d.%m"))

            bar_pc, bar_work, bar_idle = self._bars[i]
            val_pc, val_work, val_idle = self._val_labels[i]

            pc_pct = int(stats.uptime_s / max_uptime * 100)
            work_pct = int(stats.active_s / max_uptime * 100)
            idle_pct = int(stats.idle_s / max_uptime * 100)

            bar_pc.setValue(pc_pct)
            bar_work.setValue(work_pct)
            bar_idle.setValue(idle_pct)

            val_pc.setText(_fmt_hm(stats.uptime_s))
            val_work.setText(_fmt_hm(stats.active_s))
            val_idle.setText(_fmt_hm(stats.idle_s))


class RazdMonthlyStatsWidget(QWidget):
    """Ostatnie 30 dni jako tabela."""

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Data", "PC ON", "Praca", "Idle", "Prod %"])
        self._table.horizontalHeader().setStyleSheet("color: #666; font-size: 8px;")
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setStyleSheet(
            "QTableWidget {"
            "  background: #111; color: #ddd; font-size: 9px;"
            "  border: none; gridline-color: #222;"
            "}"
            "QTableWidget::item:alternate { background: #1a1a1a; }"
            "QHeaderView::section {"
            "  background: #1a1a1a; color: #666; font-size: 8px;"
            "  border: none; padding: 2px;"
            "}"
        )
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._table)

        if repo is not None:
            self.refresh()

    def set_repo(self, repo: RazdRepository) -> None:
        self._repo = repo
        self.refresh()

    def refresh(self) -> None:
        if self._repo is None:
            return

        today = datetime.date.today()
        self._table.setRowCount(0)

        for delta in range(29, -1, -1):
            d = today - datetime.timedelta(days=delta)
            stats = self._repo.compute_day_stats(d.isoformat())

            productivity = (
                round(stats.active_s / stats.uptime_s * 100)
                if stats.uptime_s > 0
                else 0
            )

            row = self._table.rowCount()
            self._table.insertRow(row)

            def _item(text: str, align: Qt.AlignmentFlag = Qt.AlignCenter) -> QTableWidgetItem:
                it = QTableWidgetItem(text)
                it.setTextAlignment(align)
                return it

            self._table.setItem(row, 0, _item(d.strftime("%d.%m"), Qt.AlignLeft | Qt.AlignVCenter))
            self._table.setItem(row, 1, _item(_fmt_hm(stats.uptime_s)))
            self._table.setItem(row, 2, _item(_fmt_hm(stats.active_s)))
            self._table.setItem(row, 3, _item(_fmt_hm(stats.idle_s)))
            self._table.setItem(row, 4, _item(f"{productivity}%"))

        self._table.resizeColumnsToContents()
