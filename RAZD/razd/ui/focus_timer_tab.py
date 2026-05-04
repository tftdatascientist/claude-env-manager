from __future__ import annotations

import datetime
from collections import Counter
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository

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


class RazdFocusTimerTab(QWidget):
    """Zakładka Focus Timer — whitelist appek, timer 30-120min, alerty."""

    # emitowany gdy app spoza whitelisty (nazwa procesu)
    focus_escaped = Signal(str)
    # emitowany po zakończeniu sesji: started_at, ended_at, duration_s, score
    focus_session_ended = Signal(str, str, int, int)

    def __init__(self, repo: RazdRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._state = _FocusState()
        self._tray: QSystemTrayIcon | None = None
        self._escape_dialog_open = False

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._on_tick)

        self._build_ui()
        self._setup_tray()
        self._update_ui()

    # -----------------------------------------------------------------
    # Budowa UI
    # -----------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        # --- lewa kolumna: whitelist ---
        wl_box = QGroupBox("Dozwolone aplikacje (whitelist)")
        wl_layout = QVBoxLayout(wl_box)

        self._wl_list = QListWidget()
        self._wl_list.setToolTip("Aplikacje dozwolone w trakcie focus session")
        wl_layout.addWidget(self._wl_list)

        wl_btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Dodaj")
        btn_add.clicked.connect(self._add_to_whitelist)
        btn_remove = QPushButton("− Usuń")
        btn_remove.clicked.connect(self._remove_from_whitelist)
        wl_btn_row.addWidget(btn_add)
        wl_btn_row.addWidget(btn_remove)
        wl_layout.addLayout(wl_btn_row)

        hint = QLabel("Wpisz nazwę procesu (np. python.exe, chrome.exe)")
        hint.setStyleSheet("color: #666; font-size: 10px;")
        wl_layout.addWidget(hint)

        splitter.addWidget(wl_box)

        # --- prawa kolumna: timer ---
        timer_box = QGroupBox("Focus Timer")
        timer_layout = QVBoxLayout(timer_box)
        timer_layout.setSpacing(14)

        # wyświetlacz czasu
        self._time_display = QLabel("00:00")
        self._time_display.setAlignment(Qt.AlignCenter)
        self._time_display.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #4A90D9; letter-spacing: 4px;"
        )
        timer_layout.addWidget(self._time_display)

        # wybór czasu
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Czas (min):"))
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(1, 180)
        self._duration_spin.setValue(25)
        self._duration_spin.setSingleStep(5)
        self._duration_spin.setFixedWidth(70)
        duration_row.addWidget(self._duration_spin)
        duration_row.addStretch()

        # szybkie przyciski presetów
        for mins in _DURATION_OPTIONS:
            btn = QPushButton(f"{mins}m")
            btn.setFixedWidth(42)
            btn.clicked.connect(lambda checked=False, m=mins: self._set_duration(m))
            duration_row.addWidget(btn)

        timer_layout.addLayout(duration_row)

        # przyciski kontrolne
        ctrl_row = QHBoxLayout()
        self._btn_start = QPushButton("▶ Start")
        self._btn_start.setStyleSheet("background: #2a6; color: white; font-weight: bold; padding: 6px 18px;")
        self._btn_start.clicked.connect(self._on_start_pause)

        self._btn_reset = QPushButton("■ Reset")
        self._btn_reset.setStyleSheet("background: #555; color: white; padding: 6px 14px;")
        self._btn_reset.clicked.connect(self._on_reset)

        ctrl_row.addStretch()
        ctrl_row.addWidget(self._btn_start)
        ctrl_row.addWidget(self._btn_reset)
        ctrl_row.addStretch()
        timer_layout.addLayout(ctrl_row)

        # status
        self._status_label = QLabel("Gotowy")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        timer_layout.addWidget(self._status_label)

        timer_layout.addStretch()
        splitter.addWidget(timer_box)
        splitter.setSizes([280, 360])

        root.addWidget(splitter)

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
            self._state.start(self._duration_spin.value())
            if self._repo:
                self._state.session_id = self._repo.start_focus_session(
                    self._state.started_at,  # type: ignore[arg-type]
                    self._state.whitelist,
                )
            self._ticker.start()
        elif self._state.state == _FocusState.RUNNING:
            self._state.pause()
        elif self._state.state == _FocusState.PAUSED:
            self._state.resume()
        self._update_ui()

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
        self._state.reset()

        self._status_label.setText(f"Session zakończona o {datetime.datetime.now().strftime('%H:%M')}!")
        self._notify_tray("RAZD", f"Focus session zakończona! Wynik: {score}/10")

        self.focus_session_ended.emit(started_at, now_str, duration_s, score)

        dlg = _FocusSummaryDialog(duration_s, score, process_counts, self._state.whitelist, self)
        dlg.exec()

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
        secs = self._state.remaining_secs
        mm = secs // 60
        ss = secs % 60
        self._time_display.setText(f"{mm:02d}:{ss:02d}")

        s = self._state.state
        if s == _FocusState.IDLE:
            self._btn_start.setText("▶ Start")
            self._btn_start.setStyleSheet("background: #2a6; color: white; font-weight: bold; padding: 6px 18px;")
            self._status_label.setText("Gotowy")
            self._duration_spin.setEnabled(True)
        elif s == _FocusState.RUNNING:
            self._btn_start.setText("⏸ Pauza")
            self._btn_start.setStyleSheet("background: #c80; color: white; font-weight: bold; padding: 6px 18px;")
            self._status_label.setText("Session aktywna ⚡")
            self._duration_spin.setEnabled(False)
        elif s == _FocusState.PAUSED:
            self._btn_start.setText("▶ Wznów")
            self._btn_start.setStyleSheet("background: #2a6; color: white; font-weight: bold; padding: 6px 18px;")
            self._status_label.setText("Wstrzymany")
            self._duration_spin.setEnabled(False)
