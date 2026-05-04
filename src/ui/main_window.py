"""Main application window with tree, editor, history, and status bar."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QFileSystemWatcher, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QSplitter, QStackedWidget,
)

_RUN_LOG = Path.home() / ".claude" / "run_log.json"

import sys as _sys
from pathlib import Path as _Path
_BB_SRC = _Path(__file__).resolve().parents[2] / "BB" / "src"
if _BB_SRC.exists() and str(_BB_SRC) not in _sys.path:
    _sys.path.insert(0, str(_BB_SRC))
_SSC_SRC = _Path(__file__).resolve().parents[2] / "SSC" / "src"
if _SSC_SRC.exists() and str(_SSC_SRC) not in _sys.path:
    _sys.path.insert(0, str(_SSC_SRC))

from src.models.resource import Resource
from src.scanner.discovery import discover_all
from src.scanner.indexer import build_tree
from src.ui.editor_panel import EditorPanel
from src.ui.tree_panel import TreePanel
from src.ui.history_panel import HistoryPanel
from src.ui.active_projects_panel import ActiveProjectsPanel
from src.ui.website_projects_panel import WebsiteProjectsPanel
from src.ui.hidden_projects_panel import HiddenProjectsPanel
from src.ui.status_bar import StatusBar
from src.ui.simulator.simulator_panel import SimulatorPanel
from src.ui.projektant_panel import ProjectantPanel
from src.ui.cc_launcher_panel import CCLauncherPanel
from src.ui.zadania_panel import ZadaniaPanel
try:
    from cm.ssc_module.views.ssc_view import SscView  # type: ignore
except ImportError as _ssc_err:
    print(f"[SSC] zakładka wyłączona: {_ssc_err}", file=_sys.stderr)
    SscView = None
try:
    from src.ssm_module.views.ssm_tab import SsmTab  # type: ignore
    from src.ssm_module.core.ssm_service import SSMService as _SSMService  # type: ignore
except ImportError as _ssm_err:
    print(f"[SSM] zakładka wyłączona: {_ssm_err}", file=_sys.stderr)
    SsmTab = None
    _SSMService = None
try:
    from coa.ui_panel import CoaPanel  # type: ignore
except ImportError as _coa_err:
    print(f"[COA] zakładka wyłączona: {_coa_err}", file=_sys.stderr)
    CoaPanel = None
try:
    from czy.widget import show_startup_factoid  # type: ignore
except ImportError as _czy_err:
    print(f"[CZY] widget wyłączony: {_czy_err}", file=_sys.stderr)
    show_startup_factoid = None
try:
    from iso.ui_panel import IsoPanel  # type: ignore
except ImportError as _iso_err:
    print(f"[ISO] zakładka wyłączona: {_iso_err}", file=_sys.stderr)
    IsoPanel = None
try:
    from ingest.ui_panel import IngestPanel  # type: ignore
except ImportError as _ingest_err:
    print(f"[Ingest] zakładka wyłączona: {_ingest_err}", file=_sys.stderr)
    IngestPanel = None
try:
    from wiki.ui_panel import WikiPanel  # type: ignore
except ImportError as _wiki_err:
    print(f"[Wiki] zakładka wyłączona: {_wiki_err}", file=_sys.stderr)
    WikiPanel = None
try:
    from src.hooker.ui.main_view import HookerView  # type: ignore
except ImportError as _hooker_err:
    print(f"[Hooker] zakładka wyłączona: {_hooker_err}", file=_sys.stderr)
    HookerView = None
try:
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent / "AUSS" / "src"))
    from asus.cm_view.asus_panel import AsusPanelWidget  # type: ignore
    _sys.path.pop(0)
except ImportError as _asus_err:
    print(f"[ASUS] panel wyłączony: {_asus_err}", file=_sys.stderr)
    AsusPanelWidget = None


class MainWindow(QMainWindow):
    """Main window: tree panel (left) + tabbed content (right) + status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Claude Manager")
        self.setMinimumSize(1000, 600)
        self.resize(1400, 800)

        self._setup_menu()
        if _SSMService is not None:
            try:
                _SSMService.instance()
            except Exception as _ssm_exc:
                print(f"[SSM] background service failed: {_ssm_exc}", file=_sys.stderr)
        self._setup_ui()
        self._show_page(self._PAGE_SESJE_CC)
        self._scan_resources()
        self._czy_dialog = None
        if show_startup_factoid is not None:
            try:
                self._czy_dialog = show_startup_factoid(parent=self)
            except Exception as _czy_exc:
                print(f"[CZY] start widget failed: {_czy_exc}", file=_sys.stderr)

    # Page indices in QStackedWidget
    _PAGE_RESOURCES = 0
    _PAGE_PROJECTS = 1
    _PAGE_ACTIVE_PROJECTS = 2
    _PAGE_WEBSITES = 3
    _PAGE_HIDDEN = 4
    _PAGE_SIMULATOR = 5
    _PAGE_PROJEKTANT = 6
    _PAGE_SESJE_CC = 7
    _PAGE_ZADANIA = 8
    _PAGE_SSC = 9
    _PAGE_SSM = 10
    _PAGE_HOOKER = 11
    _PAGE_ASUS = 12
    # BB panels start at 13 (dynamic, assigned in _setup_ui)

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == self._PAGE_ZADANIA:
            self._sync_zadania_from_active_slot()

    def _show_page_hooks(self, tab_index: int = 0) -> None:
        self._show_page(self._PAGE_HOOKER)
        if self._hooker_panel is not None:
            self._hooker_panel.setCurrentIndex(tab_index)

    def _show_ssm_tab(self) -> None:
        self._show_page(self._PAGE_SESJE_CC)
        self._cc_launcher_panel.show_ssm_tab()

    def _show_ssc_tab(self) -> None:
        self._show_page(self._PAGE_SESJE_CC)
        self._cc_launcher_panel.show_ssc_tab()

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction("&Refresh", self._refresh_all, "F5")
        file_menu.addSeparator()
        file_menu.addAction("&Quit", self.close, "Ctrl+Q")

        projekty_menu = menu_bar.addMenu("&Projekty")
        projekty_menu.addAction("&Resources", lambda: self._show_page(self._PAGE_RESOURCES), "Ctrl+1")
        projekty_menu.addAction("&Projects", lambda: self._show_page(self._PAGE_PROJECTS), "Ctrl+2")
        projekty_menu.addAction("&Active Projects", lambda: self._show_page(self._PAGE_ACTIVE_PROJECTS), "Ctrl+3")
        projekty_menu.addAction("&All Projects", lambda: self._show_page(self._PAGE_PROJECTS), "Ctrl+4")
        projekty_menu.addAction("&Hidden", lambda: self._show_page(self._PAGE_HIDDEN), "Ctrl+5")

        develop_menu = menu_bar.addMenu("&Develop")
        develop_menu.addAction("Pro&jektant", lambda: self._show_page(self._PAGE_PROJEKTANT), "Ctrl+7")
        develop_menu.addAction("&Sesje CC", lambda: self._show_page(self._PAGE_SESJE_CC), "Ctrl+8")
        develop_menu.addAction("&Zadania", lambda: self._show_page(self._PAGE_ZADANIA), "Ctrl+Z")

        bb_menu = menu_bar.addMenu("&Claude Code")
        if CoaPanel is not None:
            bb_menu.addAction("&COA — Konsultant", lambda: self._show_page(self._bb_page_coa), "Ctrl+9")
        if IsoPanel is not None:
            bb_menu.addAction("&ISO — Walidator", lambda: self._show_page(self._bb_page_iso), "Ctrl+0")
        if IngestPanel is not None:
            bb_menu.addAction("&Ingest — Dodaj do vaultu", lambda: self._show_page(self._bb_page_ingest), "Ctrl+W")
        if WikiPanel is not None:
            bb_menu.addAction("&Wiki — Przeglądarka", lambda: self._show_page(self._bb_page_wiki), "Ctrl+Shift+W")
        if show_startup_factoid is not None:
            bb_menu.addSeparator()
            bb_menu.addAction("CZ&Y wiesz że…", self._show_czy_factoid)

        websites_menu = menu_bar.addMenu("&Websites")
        websites_menu.addAction("&Strony (główny ekran)", self._launch_wms, "Ctrl+Shift+M")
        websites_menu.addSeparator()
        websites_menu.addAction("&Szablony", lambda: self._launch_wms_panel("szablony"))
        websites_menu.addAction("&Zakładki", lambda: self._launch_wms_panel("zakładki"))
        websites_menu.addAction("&Portfolio", lambda: self._launch_wms_panel("portfolio"))
        websites_menu.addSeparator()
        websites_menu.addAction("&Audit", lambda: self._launch_wms_panel("audit"))
        websites_menu.addAction("Sy&nc Notion", lambda: self._launch_wms_panel("sync"))

        webdev_menu = menu_bar.addMenu("&Web_Dev")
        webdev_menu.addAction("&Editor", lambda: self._launch_wms_panel("editor"))
        webdev_menu.addSeparator()
        webdev_menu.addAction("Etap &0 — Brief", lambda: self._launch_wms_panel("brief"))
        webdev_menu.addAction("Etap &1 — WCS Init", lambda: self._launch_wms_panel("etap1"))

        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction("&Simulator", lambda: self._show_page(self._PAGE_SIMULATOR), "Ctrl+6")
        if AsusPanelWidget is not None:
            tools_menu.addAction("&ASUS — Self Update", lambda: self._show_page(self._PAGE_ASUS), "Ctrl+A")

        hooks_menu = menu_bar.addMenu("&Hooks")
        hooks_menu.addAction("&Finder — szukaj hooków", lambda: self._show_page_hooks(0), "Ctrl+H")
        hooks_menu.addAction("&Setup — edytuj hooki", lambda: self._show_page_hooks(1), "Ctrl+Shift+H")
        hooks_menu.addSeparator()
        hooks_menu.addAction("&Wiki — przewodnik", lambda: self._show_page_hooks(2))
        hooks_menu.addAction("&Sound — dźwięki", lambda: self._show_page_hooks(3))

        sss_menu = menu_bar.addMenu("&SSS")
        sss_menu.addAction("&Monitor", self._show_ssm_tab)
        sss_menu.addAction("&Converter", self._show_ssc_tab)
        tools_menu.addSeparator()
        tost_menu = tools_menu.addMenu("TOST — Token Monitor")
        tost_menu.addAction("&Monitor (Dashboard + Collector)", self._tost_monitor)
        tost_menu.addAction("&Simulator (Cost Simulation)", self._tost_sim)
        tost_menu.addAction("&Duel (Profile Comparison)", self._tost_duel)
        tost_menu.addAction("&Trainer (Context Engineering)", self._tost_train)
        tost_menu.addSeparator()
        tost_menu.addAction("Notion Sync — &Continuous", self._tost_notion_sync)
        tost_menu.addAction("Notion Sync — &Once", self._tost_notion_sync_once)

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction("Reset category &colors", self._reset_colors)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction("&About", self._show_about)

    def _setup_ui(self) -> None:
        self._tree_panel = TreePanel()
        self._editor_panel = EditorPanel()
        self._history_panel = HistoryPanel()
        self._active_projects_panel = ActiveProjectsPanel()
        self._website_projects_panel = WebsiteProjectsPanel()
        self._hidden_projects_panel = HiddenProjectsPanel()
        self._simulator_panel = SimulatorPanel()
        self._projektant_panel = ProjectantPanel()
        self._cc_launcher_panel = CCLauncherPanel()
        self._zadania_panel = ZadaniaPanel()
        self._ssc_panel = SscView() if SscView is not None else None
        self._ssm_panel = SsmTab() if SsmTab is not None else None
        self._hooker_panel = HookerView() if HookerView is not None else None
        self._asus_panel = AsusPanelWidget() if AsusPanelWidget is not None else None
        self._coa_panel = CoaPanel() if CoaPanel is not None else None
        self._iso_panel = IsoPanel() if IsoPanel is not None else None
        self._ingest_panel = IngestPanel() if IngestPanel is not None else None
        self._wiki_panel = WikiPanel() if WikiPanel is not None else None

        # Resources view: tree (left) + editor (right)
        self._resources_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._resources_splitter.addWidget(self._tree_panel)
        self._resources_splitter.addWidget(self._editor_panel)
        self._resources_splitter.setSizes([320, 900])
        self._resources_splitter.setStretchFactor(0, 0)
        self._resources_splitter.setStretchFactor(1, 1)

        # Connect tree signals
        self._tree_panel.resource_selected.connect(self._on_resource_selected)
        self._tree_panel.project_detail_requested.connect(self._on_project_detail)
        self._tree_panel.refresh_requested.connect(self._scan_resources)

        # Stacked widget — no tab bar, menu-driven navigation
        self._stack = QStackedWidget()
        self._stack.addWidget(self._resources_splitter)       # 0 = Resources
        self._stack.addWidget(self._history_panel)            # 1 = Projects
        self._stack.addWidget(self._active_projects_panel)    # 2 = Active Projects
        self._stack.addWidget(self._website_projects_panel)   # 3 = Websites
        self._stack.addWidget(self._hidden_projects_panel)    # 4 = Hidden
        self._stack.addWidget(self._simulator_panel)          # 5 = Simulator
        self._stack.addWidget(self._projektant_panel)         # 6 = Projektant
        self._stack.addWidget(self._cc_launcher_panel)        # 7 = Sesje CC
        self._stack.addWidget(self._zadania_panel)             # 8 = Zadania
        # SSC: zawsze rezerwujemy slot 9 — placeholder QWidget gdy moduł nieosiągalny,
        # żeby utrzymać stabilne indeksy BB poniżej.
        from PySide6.QtWidgets import QWidget as _QWidget
        self._stack.addWidget(self._ssc_panel if self._ssc_panel is not None else _QWidget())  # 9 = SSC
        self._stack.addWidget(self._ssm_panel if self._ssm_panel is not None else _QWidget())  # 10 = SSM
        self._stack.addWidget(self._hooker_panel if self._hooker_panel is not None else _QWidget())  # 11 = Hooker
        self._stack.addWidget(self._asus_panel if self._asus_panel is not None else _QWidget())    # 12 = ASUS

        # BB panels — track indices dynamically starting at 13
        bb_idx = 13
        self._bb_page_coa = -1
        self._bb_page_iso = -1
        self._bb_page_ingest = -1
        self._bb_page_wiki = -1
        if self._coa_panel is not None:
            self._stack.addWidget(self._coa_panel)
            self._bb_page_coa = bb_idx; bb_idx += 1
        if self._iso_panel is not None:
            self._stack.addWidget(self._iso_panel)
            self._bb_page_iso = bb_idx; bb_idx += 1
        if self._ingest_panel is not None:
            self._stack.addWidget(self._ingest_panel)
            self._bb_page_ingest = bb_idx; bb_idx += 1
        if self._wiki_panel is not None:
            self._stack.addWidget(self._wiki_panel)
            self._bb_page_wiki = bb_idx; bb_idx += 1

        self.setCentralWidget(self._stack)

        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)

        # Obserwuj run_log.json — powiadomienia o skryptach Pythona
        self._run_log_watcher = QFileSystemWatcher(self)
        if _RUN_LOG.exists():
            self._run_log_watcher.addPath(str(_RUN_LOG))
        self._run_log_watcher.fileChanged.connect(self._on_run_log_changed)
        # Jeśli plik jeszcze nie istnieje, sprawdzaj co 10s aż powstanie
        self._run_log_poll = QTimer(self)
        self._run_log_poll.setInterval(10_000)
        self._run_log_poll.timeout.connect(self._run_log_poll_tick)
        if not _RUN_LOG.exists():
            self._run_log_poll.start()

        # Connect signals
        self._projektant_panel.project_ready.connect(self._on_project_ready)
        self._history_panel.active_projects_changed.connect(self._active_projects_panel.refresh)
        self._history_panel.website_projects_changed.connect(self._website_projects_panel.refresh)
        self._history_panel.project_hidden.connect(self._hidden_projects_panel.refresh)
        self._hidden_projects_panel.project_unhidden.connect(self._history_panel.refresh)

    def _scan_resources(self) -> None:
        """Scan all resources and update tree + status bar."""
        self._status_bar.set_status("Scanning resources...")

        managed, user, projects, external = discover_all()

        total = (
            len(managed)
            + len(user)
            + sum(len(p.resources) for p in projects)
            + len(external)
        )
        self._status_bar.set_status("Ready")
        self._status_bar.show_scan_summary(total)

        tree_root = build_tree(managed, user, projects, external)
        self._tree_panel.populate(tree_root)

        if self._editor_panel._current_resource is None:
            self._editor_panel.show_welcome(
                managed=len(managed),
                user=len(user),
                projects=len(projects),
                external=len(external),
            )

    def _sync_zadania_from_active_slot(self) -> None:
        """Wczytaj projekt aktywnego slotu CC do ZadaniaPanel (jeśli ustawiony)."""
        try:
            active_slot = self._cc_launcher_panel._slots[
                self._cc_launcher_panel._slot_tabs.currentIndex()
            ]
            project_path = active_slot.get_config().project_path.strip()
        except Exception:
            return
        if project_path:
            self._zadania_panel.load_from_project(project_path, silent=True)

    def _refresh_all(self) -> None:
        """Refresh resources, history, active projects, and websites."""
        self._scan_resources()
        self._history_panel.refresh()
        self._active_projects_panel.refresh()
        self._website_projects_panel.refresh()
        self._hidden_projects_panel.refresh()

    def _on_project_ready(self, path) -> None:
        """Projektant created a new project — assign to Sesje CC and switch there."""
        from pathlib import Path
        slot = self._cc_launcher_panel.assign_project(Path(path))
        self._show_page(self._PAGE_SESJE_CC)

    def _on_resource_selected(self, resource: Resource) -> None:
        """Handle resource selection from tree."""
        self._show_page(self._PAGE_RESOURCES)
        self._editor_panel.show_resource(resource)
        self._status_bar.show_resource_info(resource)

    def _on_project_detail(self, proj: dict) -> None:
        """Handle project selection from All Projects list."""
        self._show_page(self._PAGE_RESOURCES)
        self._editor_panel.show_project_detail(proj)

    def _reset_colors(self) -> None:
        """Reset all category colors to defaults and refresh tree."""
        from src.utils.colors import reset_colors
        reset_colors()
        self._scan_resources()

    def _show_czy_factoid(self) -> None:
        """Re-open CZY dialog on demand (View menu)."""
        if show_startup_factoid is None:
            return
        try:
            self._czy_dialog = show_startup_factoid(parent=self)
        except Exception as _exc:
            print(f"[CZY] show failed: {_exc}", file=_sys.stderr)

    # --- WMS launcher ---

    def _launch_wms(self) -> None:
        from src.utils.wms import is_wms_installed, launch_wms
        if not is_wms_installed():
            QMessageBox.warning(
                self, "WMS",
                "WMS nie jest zainstalowany lub venv nie istnieje.\n\n"
                "Oczekiwana lokalizacja:\n"
                "~/Documents/.MD/PARA/SER/CLAUDE CODE/WMS/.venv/",
            )
            return
        proc = launch_wms()
        if proc is None:
            QMessageBox.critical(self, "WMS", "Nie udało się uruchomić WMS.")
        else:
            self._status_bar.set_status(f"WMS uruchomiony (PID {proc.pid})")

    def _launch_wms_panel(self, panel: str) -> None:
        from src.utils.wms import is_wms_installed, launch_wms_panel
        if not is_wms_installed():
            QMessageBox.warning(
                self, "WMS",
                "WMS nie jest zainstalowany lub venv nie istnieje.\n\n"
                "Oczekiwana lokalizacja:\n"
                "~/Documents/.MD/PARA/SER/CLAUDE CODE/WMS/.venv/",
            )
            return
        proc = launch_wms_panel(panel)
        if proc is None:
            QMessageBox.critical(self, "WMS", f"Nie udało się uruchomić WMS ({panel}).")
        else:
            self._status_bar.set_status(f"WMS [{panel}] uruchomiony (PID {proc.pid})")

    # --- TOST launchers ---

    def _tost_launch(self, launcher_func, label: str) -> None:
        """Generic TOST launcher with error handling."""
        from src.utils.tost import is_tost_installed
        if not is_tost_installed():
            QMessageBox.warning(
                self, "TOST",
                "TOST nie jest zainstalowany lub katalog projektu nie istnieje.\n\n"
                "Oczekiwana lokalizacja:\n"
                "~/Documents/.MD/PARA/SER/10_PROJEKTY/SIDE/PRAWY/",
            )
            return
        proc = launcher_func()
        if proc is None:
            QMessageBox.critical(self, "TOST", f"Nie udalo sie uruchomic TOST {label}.")
        else:
            self._status_bar.set_status(f"TOST {label} uruchomiony (PID {proc.pid})")

    def _tost_monitor(self) -> None:
        from src.utils.tost import launch_monitor
        self._tost_launch(launch_monitor, "Monitor")

    def _tost_sim(self) -> None:
        from src.utils.tost import launch_sim
        self._tost_launch(launch_sim, "Simulator")

    def _tost_duel(self) -> None:
        from src.utils.tost import launch_duel
        self._tost_launch(launch_duel, "Duel")

    def _tost_train(self) -> None:
        from src.utils.tost import launch_train
        self._tost_launch(launch_train, "Trainer")

    def _tost_notion_sync(self) -> None:
        from src.utils.tost import launch_notion_sync
        self._tost_launch(lambda: launch_notion_sync(once=False), "Notion Sync")

    def _tost_notion_sync_once(self) -> None:
        from src.utils.tost import launch_notion_sync
        self._tost_launch(lambda: launch_notion_sync(once=True), "Notion Sync (once)")

    def _run_log_poll_tick(self) -> None:
        """Sprawdzaj co 10s czy run_log.json już istnieje i podepnij watcher."""
        if _RUN_LOG.exists():
            self._run_log_watcher.addPath(str(_RUN_LOG))
            self._run_log_poll.stop()

    def _on_run_log_changed(self, path: str) -> None:
        """Odczytaj ostatni wpis z run_log.json i pokaż w status barze."""
        log_path = Path(path)
        # QFileSystemWatcher traci ścieżkę po nadpisaniu pliku — re-add
        if path not in self._run_log_watcher.files():
            if log_path.exists():
                self._run_log_watcher.addPath(path)
        if not log_path.exists():
            return
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list) or not entries:
                return
            last = entries[-1]
            self._status_bar.show_script_running(
                cmd=last.get("cmd", ""),
                ts=last.get("ts", ""),
            )
        except Exception:
            pass

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Claude Manager",
            "Claude Manager v0.2\n\n"
            "Centralna aplikacja zarządzająca wszystkimi narzędziami\n"
            "i zasobami Claude Code z jednego miejsca.",
        )
