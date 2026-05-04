from __future__ import annotations

import datetime
import sys as _sys
from pathlib import Path as _Path
# ASUS:inject:begin
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent / ".asus"))
try:
    from interface_pyside_menu import AsusNotesTab as _AsusNotesTab  # type: ignore
    _ASUS_OK = True
except ImportError:
    _ASUS_OK = False
# ASUS:inject:end

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QSystemTrayIcon,
    QTabWidget,
    QToolBar,
    QWidget,
)

from razd import autostart
from razd.agent.client import RazdAgentThread
from razd.config.settings import RazdSettings
from razd.db.repository import RazdRepository
from razd.notion.sync_worker import RazdNotionSyncThread
from razd.tracker.poller import RazdPoller
from razd.ui.dialogs import ask_user_blocking
from razd.ui.focus_timer_tab import RazdFocusTimerTab
from razd.ui.local_tab import RazdLocalTab
from razd.ui.time_tracking_tab import RazdTimeTrackingTab
from razd.ui.timeline_tab import RazdTimelineTab
from razd.ui.www_tab import RazdWwwTab


def _fmt_uptime(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m" if m else f"{secs}s"


def _make_tray_icon() -> QIcon:
    """Tworzy ikonkę tray — litera R na niebieskim tle (działa na Windows bez theme)."""
    px = QPixmap(32, 32)
    px.fill(QColor("#1565C0"))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("white"))
    font = QFont("Arial", 17, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "R")
    painter.end()
    return QIcon(px)


class RazdMainWindow(QMainWindow):
    """Główne okno modułu RAZD — spina Tracker → Agent → UI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAZD — Time Tracking & Focus")
        self.setMinimumSize(900, 600)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowIcon(_make_tray_icon())

        self._settings = RazdSettings.load()
        self._settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._repo = RazdRepository(self._settings.db_path)

        self._agent_thread = RazdAgentThread(
            repo=self._repo,
            ask_user_cb=lambda subject, question: ask_user_blocking(subject, "process", question),
        )

        self._poller = RazdPoller(
            repo=self._repo,
            work_interval_min=self._settings.break_interval_min,
        )
        self._poller.event_ready.connect(self._on_event)
        self._poller.cc_session_started.connect(self._on_cc_started)
        self._poller.cc_session_ended.connect(self._on_cc_ended)
        self._poller.break_due.connect(self._on_break_due)
        self._poller.distraction_alert.connect(self._on_distraction_alert)
        self._poller.distraction_score.connect(self._on_distraction_score)

        n = self._settings.notion
        self._notion_thread: RazdNotionSyncThread | None = (
            RazdNotionSyncThread(
                repo=self._repo,
                interval_mins=n.sync_interval_mins,
                export_urls=n.export_urls,
            )
            if n.enabled
            else None
        )

        tabs = QTabWidget()
        self._tt_tab = RazdTimeTrackingTab(self._repo)
        self._tt_tab.set_poller(self._poller)
        self._focus_tab = RazdFocusTimerTab(repo=self._repo)
        self._focus_tab.focus_session_ended.connect(self._on_focus_session_ended)
        self._timeline_tab = RazdTimelineTab(repo=self._repo)
        self._www_tab = RazdWwwTab(repo=self._repo)
        self._local_tab = RazdLocalTab(repo=self._repo)
        tabs.addTab(self._tt_tab, "Time Tracking")
        tabs.addTab(self._focus_tab, "Focus Timer")
        tabs.addTab(self._timeline_tab, "Timeline")
        tabs.addTab(self._www_tab, "WWW")
        tabs.addTab(self._local_tab, "Local")
        # ASUS:inject:begin
        if _ASUS_OK:
            tabs.addTab(_AsusNotesTab(_Path(__file__).resolve().parent.parent.parent), "ASUS")
        # ASUS:inject:end
        self.setCentralWidget(tabs)

        self._app_start_ts = datetime.datetime.now().timestamp()
        self._setup_toolbar()
        self._setup_tray()
        self._update_uptimes()   # pierwsze wypełnienie etykiet (po setup_tray)

    # --- public API ---

    def start_minimized(self) -> None:
        """Uruchamia serwisy w tle bez pokazywania okna — tryb autostart."""
        self._start_services()
        self._tray.show()

    # --- toolbar ---

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Główny", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # ── Liczniki czasu ─────────────────────────────────────────────
        self._app_uptime_lbl = QLabel("App: —")
        self._app_uptime_lbl.setToolTip("Czas działania RAZD dzisiaj (od 00:00 lub od startu)")
        self._app_uptime_lbl.setStyleSheet(
            "color: #5c5; font-size: 11px; font-weight: bold; padding: 0 10px;"
        )
        toolbar.addWidget(self._app_uptime_lbl)

        toolbar.addSeparator()

        self._pc_uptime_lbl = QLabel("PC: —")
        self._pc_uptime_lbl.setToolTip("Czas działania komputera dzisiaj (od 00:00 lub od startu)")
        self._pc_uptime_lbl.setStyleSheet(
            "color: #4A90D9; font-size: 11px; font-weight: bold; padding: 0 10px;"
        )
        toolbar.addWidget(self._pc_uptime_lbl)

        toolbar.addSeparator()

        # timer odświeżający liczniki co 30s
        self._uptime_timer = QTimer(self)
        self._uptime_timer.timeout.connect(self._update_uptimes)
        self._uptime_timer.start(30_000)

        # ── spacer + przycisk tło ──────────────────────────────────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        bg_action = QAction("⬇ Przejdź w tło", self)
        bg_action.setToolTip("Ukryj okno — tracker i agent działają dalej w tle")
        bg_action.triggered.connect(self._go_to_background)
        toolbar.addAction(bg_action)

    def _update_uptimes(self) -> None:
        now = datetime.datetime.now()
        midnight_ts = datetime.datetime.combine(now.date(), datetime.time.min).timestamp()
        now_ts = now.timestamp()

        # App: od 00:00 lub od startu (cokolwiek późniejsze)
        app_since = max(self._app_start_ts, midnight_ts)
        app_secs = int(now_ts - app_since)

        # PC: od 00:00 lub od bootu (cokolwiek późniejsze)
        boot_ts = psutil.boot_time()
        pc_since = max(boot_ts, midnight_ts)
        pc_secs = int(now_ts - pc_since)

        self._app_uptime_lbl.setText(f"App: {_fmt_uptime(app_secs)}")
        self._pc_uptime_lbl.setText(f"PC: {_fmt_uptime(pc_secs)}")

        self._tray.setToolTip(
            f"RAZD — Time Tracking & Focus\n"
            f"App: {_fmt_uptime(app_secs)}  |  PC: {_fmt_uptime(pc_secs)}"
        )

    # --- tray ---

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("RAZD — Time Tracking & Focus")

        menu = QMenu()

        show_action = QAction("Pokaż okno", menu)
        show_action.triggered.connect(self._restore_from_background)
        menu.addAction(show_action)

        menu.addSeparator()

        self._autostart_action = QAction("", menu)
        self._autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self._autostart_action)
        self._refresh_autostart_label()

        shortcut_action = QAction("Skrót na pulpicie (utwórz / aktualizuj)", menu)
        shortcut_action.triggered.connect(self._create_desktop_shortcut)
        menu.addAction(shortcut_action)

        menu.addSeparator()

        quit_action = QAction("Zakończ RAZD", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)

    def _refresh_autostart_label(self) -> None:
        if autostart.is_enabled():
            self._autostart_action.setText("✓ Autostart z Windows (wyłącz)")
        else:
            self._autostart_action.setText("Autostart z Windows (włącz)")

    def _toggle_autostart(self) -> None:
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        self._refresh_autostart_label()

    def _create_desktop_shortcut(self) -> None:
        from razd.shortcut import create_shortcut
        try:
            _path, msg = create_shortcut()
            self._tray.showMessage(
                "RAZD — skrót na pulpicie",
                msg,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
        except Exception as exc:
            self._tray.showMessage(
                "RAZD — błąd",
                f"Nie udało się utworzyć skrótu:\n{exc}",
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )

    # --- serwisy ---

    def _start_services(self) -> None:
        if not self._agent_thread.isRunning():
            self._agent_thread.start()
        if not self._poller._timer.isActive():
            self._poller.start()
        if self._notion_thread and not self._notion_thread.isRunning():
            self._notion_thread.start()

    # --- tło / przywracanie ---

    def _go_to_background(self) -> None:
        self._tray.show()
        self._tray.showMessage(
            "RAZD działa w tle",
            "Tracker i agent są aktywne. Kliknij ikonę w zasobniku, by wrócić.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )
        self.hide()

    def _restore_from_background(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit(self) -> None:
        self._poller.stop()
        if self._notion_thread:
            self._notion_thread.stop_worker()
        self._tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_background()

    # --- Qt events ---

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._tray.show()
        self._start_services()

    def closeEvent(self, event) -> None:
        # X na oknie = przejście w tło, nie zamknięcie
        event.ignore()
        self._go_to_background()

    def _on_break_due(self, minutes: int) -> None:
        self._tt_tab.on_break_due(minutes)
        self._tray.showMessage(
            "RAZD — Czas na przerwę!",
            f"Pracujesz już {minutes} min bez przerwy. Wstań, rozciągnij się!",
            QSystemTrayIcon.MessageIcon.Information,
            8000,
        )

    def _on_distraction_alert(self, spm: float) -> None:
        self._tt_tab.on_distraction_alert(spm)
        self._tray.showMessage(
            "RAZD — Duże rozproszenie",
            f"Przełączasz aplikacje {spm:.1f}×/min. Skup się na jednym zadaniu.",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def _on_distraction_score(self, spm: float) -> None:
        self._tt_tab.on_distraction_score(spm)

    def _on_cc_started(self, project_path: str, session_id: int) -> None:
        self._tt_tab.on_cc_session_started(project_path, session_id)

    def _on_cc_ended(self, project_path: str, duration_s: int) -> None:
        self._tt_tab.on_cc_session_ended(project_path, duration_s)

    def _on_focus_session_ended(self, started_at: str, ended_at: str, duration_s: int, score: int) -> None:
        self._tt_tab.on_focus_session(started_at, ended_at, duration_s, score)

    def _on_event(self, dto) -> None:
        self._agent_thread.enqueue_event(dto)
        self._tt_tab.on_event(dto)
        self._local_tab.on_event(dto)
        if dto.process_name and dto.event_type != "idle":
            self._focus_tab.check_active_app(dto.process_name)
