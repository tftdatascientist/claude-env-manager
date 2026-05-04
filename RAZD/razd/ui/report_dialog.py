from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import DailyReport


def _fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


class RazdDailyReportDialog(QDialog):
    """Dialog z pełną analityką dnia — produktywność, focus, CC, przerwy, rozproszenie."""

    def __init__(self, report: DailyReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"RAZD — Raport dnia: {report.date}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(540)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(12)

        # --- Productivity score ---
        score = report.productivity_score
        score_color = "#2a6" if score >= 70 else ("#c80" if score >= 40 else "#c33")
        score_lbl = QLabel(
            f"<span style='font-size:46px;font-weight:bold;color:{score_color};'>{score}</span>"
            f"<span style='font-size:18px;color:#888;'>/100 — wynik produktywności</span>"
        )
        score_lbl.setAlignment(Qt.AlignCenter)
        score_lbl.setTextFormat(Qt.RichText)
        root.addWidget(score_lbl)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(score)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background:{score_color}; border-radius:4px; }}"
            "QProgressBar { border-radius:4px; background:#333; }"
        )
        root.addWidget(bar)

        # --- Czas pracy ---
        time_box = QGroupBox("Czas pracy")
        time_layout = QHBoxLayout(time_box)
        for label, value, color in [
            ("Aktywny", _fmt_time(report.total_active_s), "#4A90D9"),
            ("Produktywny", _fmt_time(report.productive_s), "#2a6"),
            ("Idle", _fmt_time(report.idle_s), "#666"),
        ]:
            col = QVBoxLayout()
            val_lbl = QLabel(value)
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet(f"font-size:20px;font-weight:bold;color:{color};")
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#888;font-size:11px;")
            col.addWidget(val_lbl)
            col.addWidget(lbl)
            time_layout.addLayout(col)
        root.addWidget(time_box)

        # --- Top kategorie ---
        if report.top_categories:
            cat_box = QGroupBox("Top kategorie")
            cat_layout = QVBoxLayout(cat_box)
            total = report.total_active_s or 1
            for name, secs in report.top_categories:
                row = QHBoxLayout()
                name_lbl = QLabel(name)
                name_lbl.setFixedWidth(160)
                pct = round(secs / total * 100)
                pct_bar = QProgressBar()
                pct_bar.setRange(0, 100)
                pct_bar.setValue(pct)
                pct_bar.setTextVisible(False)
                pct_bar.setFixedHeight(8)
                pct_bar.setStyleSheet(
                    "QProgressBar::chunk { background:#4A90D9; border-radius:3px; }"
                    "QProgressBar { background:#333; border-radius:3px; }"
                )
                time_lbl = QLabel(f"{_fmt_time(secs)} ({pct}%)")
                time_lbl.setFixedWidth(90)
                time_lbl.setStyleSheet("color:#aaa;font-size:11px;")
                row.addWidget(name_lbl)
                row.addWidget(pct_bar, 1)
                row.addWidget(time_lbl)
                cat_layout.addLayout(row)
            root.addWidget(cat_box)

        # --- Focus sessions ---
        focus_box = QGroupBox(f"Sesje Focus ({len(report.focus_sessions)})")
        focus_layout = QVBoxLayout(focus_box)
        if report.focus_sessions:
            focus_list = QListWidget()
            focus_list.setMaximumHeight(120)
            for fs in report.focus_sessions:
                if fs.ended_at:
                    score_val = fs.score if fs.score is not None else "?"
                    score_c = "#2a6" if isinstance(fs.score, int) and fs.score >= 7 else "#c80"
                    item = QListWidgetItem(
                        f"  {fs.started_at[11:16]} → {fs.ended_at[11:16]}"
                        f"  ·  {_fmt_time(fs.duration_s)}"
                        f"  ·  wynik: {score_val}/10"
                    )
                    item.setForeground(QColor(score_c))
                    focus_list.addItem(item)
            focus_layout.addWidget(focus_list)
        else:
            focus_layout.addWidget(QLabel("Brak sesji focus dzisiaj."))
        root.addWidget(focus_box)

        # --- CC sessions ---
        cc_box = QGroupBox(f"Sesje Claude Code ({len(report.cc_sessions)})")
        cc_layout = QVBoxLayout(cc_box)
        if report.cc_sessions:
            cc_list = QListWidget()
            cc_list.setMaximumHeight(100)
            for cs in report.cc_sessions:
                proj = cs.project_path.replace("\\", "/").rstrip("/").split("/")[-1] or cs.project_path
                ended = cs.ended_at[11:16] if cs.ended_at else "aktywna"
                item = QListWidgetItem(
                    f"  {cs.started_at[11:16]} → {ended}"
                    f"  ·  {_fmt_time(cs.duration_s)}"
                    f"  ·  {proj}"
                )
                item.setForeground(QColor("#22aa55"))
                cc_list.addItem(item)
            cc_layout.addWidget(cc_list)
        else:
            cc_layout.addWidget(QLabel("Brak sesji CC dzisiaj."))
        root.addWidget(cc_box)

        # --- Przerwy ---
        suggested = sum(1 for b in report.break_events if b.event_type == "suggested")
        taken = sum(1 for b in report.break_events if b.event_type == "taken")
        break_box = QGroupBox(f"Przerwy — zasugerowane: {suggested}, wzięte: {taken}")
        break_layout = QVBoxLayout(break_box)
        if report.break_events:
            compliance = round(taken / suggested * 100) if suggested else 100
            comp_row = QHBoxLayout()
            comp_lbl = QLabel(f"Compliance przerw: {compliance}%")
            comp_color = "#2a6" if compliance >= 80 else ("#c80" if compliance >= 50 else "#c33")
            comp_lbl.setStyleSheet(f"color:{comp_color};font-size:13px;font-weight:bold;")
            comp_row.addWidget(comp_lbl)
            break_layout.addLayout(comp_row)
        else:
            break_layout.addWidget(QLabel("Brak danych o przerwach."))
        root.addWidget(break_box)

        # --- Rozproszenie ---
        dist_box = QGroupBox(f"Rozproszenie ({len(report.distraction_events)} alertów)")
        dist_layout = QVBoxLayout(dist_box)
        if report.distraction_events:
            avg_spm = sum(d.switches_per_min for d in report.distraction_events) / len(report.distraction_events)
            dist_layout.addWidget(QLabel(f"Śr. przełączeń/min podczas alertów: {avg_spm:.1f}"))
        else:
            dist_layout.addWidget(QLabel("Brak alertów rozproszenia — świetna robota!"))
        root.addWidget(dist_box)

        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons)
