"""Tabela wynikow symulacji — dwa osobne panele per profil."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.simulator.models import DualSimResult, SimResult


def _fmt_k(tok: int) -> str:
    return f"{tok / 1000:.1f}k" if tok >= 1000 else str(tok)


def _fmt_cost(usd: float) -> str:
    if usd < 0.001:
        return f"${usd * 1000:.3f}m"
    return f"${usd:.4f}"


def _delta_pct(a: float, b: float) -> str:
    if b == 0:
        return "—"
    pct = (a - b) / b * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


_COLS = ["#", "Ctx", "Cost", "Cumulative", "AC"]
_FONT_MONO9 = QFont("Consolas", 9)
_TABLE_STYLE = (
    "QTableWidget { background-color: #1e1e1e; color: #cccccc; "
    "gridline-color: #333333; alternate-background-color: #252526; }"
    "QHeaderView::section { background-color: #2d2d2d; color: #569cd6; "
    "padding: 4px; border: none; }"
)


class _ProfilePanel(QWidget):
    """Panel wyników jednego profilu: nagłówek z nazwą + tabela."""

    def __init__(self, side_color: str, parent=None) -> None:
        super().__init__(parent)
        self._side_color = side_color
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        self._name_label = QLabel("—")
        self._name_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet(
            f"background-color: #1e1e1e; color: {self._side_color}; "
            "padding: 4px 8px; border-bottom: 2px solid "
            f"{self._side_color};"
        )
        vbox.addWidget(self._name_label)

        self._summary_label = QLabel("—")
        self._summary_label.setFont(_FONT_MONO9)
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._summary_label.setStyleSheet("color: #808080; padding: 2px 4px;")
        vbox.addWidget(self._summary_label)

        self._table = QTableWidget(0, len(_COLS))
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.setFont(_FONT_MONO9)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(_TABLE_STYLE)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        vbox.addWidget(self._table, stretch=1)

    def set_profile_name(self, name: str) -> None:
        self._name_label.setText(name)

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._summary_label.setText("—")

    def _fill_row(self, row: int, sr, highlight: bool = False) -> None:
        ac_flag = "⚡" if sr.autocompact_fired else ""
        cells = [
            (str(sr.scene_number),              "#cccccc"),
            (_fmt_k(sr.total_ctx_tokens),       "#b5cea8"),
            (_fmt_cost(sr.cost_usd),            "#ce9178"),
            (_fmt_cost(sr.cumulative_cost_usd), "#d4d4d4"),
            (ac_flag,                            "#f44747"),
        ]
        for j, (text, color) in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setForeground(QColor(color))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if sr.autocompact_fired:
                item.setBackground(QColor("#3a2000"))
            elif highlight:
                item.setBackground(QColor("#1a3a5c"))
            self._table.setItem(row, j, item)

    def show_step(self, result: SimResult, step: int) -> None:
        n = len(result.scene_results)
        if step >= n:
            return
        self.set_profile_name(result.profile.name)
        if self._table.rowCount() < step + 1:
            self._table.setRowCount(step + 1)
        if step > 0:
            self._fill_row(step - 1, result.scene_results[step - 1])
        self._fill_row(step, result.scene_results[step], highlight=True)
        self._table.scrollToItem(self._table.item(step, 0))
        cum = result.scene_results[step].cumulative_cost_usd
        self._summary_label.setText(f"Scena {step + 1}/{n}  |  Łącznie: {_fmt_cost(cum)}")

    def show_result(self, result: SimResult) -> None:
        self.set_profile_name(result.profile.name)
        self._table.setRowCount(len(result.scene_results))
        for i, sr in enumerate(result.scene_results):
            self._fill_row(i, sr)
        self._summary_label.setText(
            f"Łącznie: {_fmt_cost(result.total_cost_usd)}  |  "
            f"Autocompacty: {result.autocompact_count}"
        )


class ResultsView(QWidget):
    """Dwa panele wyników: lewy = profil A, prawy = profil B."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._panel_a = _ProfilePanel(side_color="#569cd6")
        self._panel_b = _ProfilePanel(side_color="#98c379")

        self._splitter.addWidget(self._panel_a)
        self._splitter.addWidget(self._panel_b)
        self._splitter.setSizes([1, 1])

        layout.addWidget(self._splitter, stretch=1)

        # Pasek podsumowania różnicy
        self._diff_label = QLabel("—")
        self._diff_label.setFont(_FONT_MONO9)
        self._diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._diff_label.setStyleSheet(
            "color: #cccccc; background-color: #252526; padding: 3px 6px;"
        )
        layout.addWidget(self._diff_label)

    def show_step(self, dual: DualSimResult, step: int) -> None:
        self._panel_a.show_step(dual.result_a, step)
        self._panel_b.show_step(dual.result_b, step)
        self._diff_label.setText("Symulacja w toku…")

    def show_dual(self, dual: DualSimResult) -> None:
        self._panel_a.show_result(dual.result_a)
        self._panel_b.show_result(dual.result_b)
        winner = dual.winner
        savings = dual.savings_usd
        pct = dual.savings_pct
        self._diff_label.setText(
            f"Winner: {winner}  |  Oszczednosc: {_fmt_cost(savings)} ({pct:.1f}%)"
        )

    def show_single(self, result: SimResult) -> None:
        self._panel_a.show_result(result)
        self._panel_b.clear()
        self._panel_b.set_profile_name("—")
        self._diff_label.setText("Tryb pojedynczy")

    def clear(self) -> None:
        self._panel_a.clear()
        self._panel_b.clear()
        self._diff_label.setText("—")
