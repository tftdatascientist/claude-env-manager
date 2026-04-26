"""Main application window with tree, editor, history, and status bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QStackedWidget,
)

from src.models.resource import Resource
from src.scanner.discovery import discover_all
from src.ui.editor_panel import EditorPanel
from src.ui.history_panel import HistoryPanel
from src.ui.active_projects_panel import ActiveProjectsPanel
from src.ui.website_projects_panel import WebsiteProjectsPanel
from src.ui.hidden_projects_panel import HiddenProjectsPanel
from src.ui.status_bar import StatusBar
from src.ui.simulator.simulator_panel import SimulatorPanel
from src.ui.projektant_panel import ProjectantPanel
from src.ui.cc_launcher_panel import CCLauncherPanel
from src.ui.zadania_panel import ZadaniaPanel

import sys as _sys
from pathlib import Path as _Path
_BB_SRC = _Path(__file__).resolve().parents[2] / "BB" / "src"
if _BB_SRC.exists() and str(_BB_SRC) not in _sys.path:
    _sys.path.insert(0, str(_BB_SRC))
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


class MainWindow(QMainWindow):
    """Main window: tree panel (left) + tabbed content (right) + status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Claude Manager")
        self.setMinimumSize(1000, 600)
        self.resize(1400, 800)

        self._setup_menu()
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
    # BB panels start at 9 (dynamic, assigned in _setup_ui)

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == self._PAGE_ZADANIA:
            self._sync_zadania_from_active_slot()

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
        tools_menu.addSeparator()
        cc_panel_menu = tools_menu.addMenu("&cc-panel")
        cc_panel_menu.addAction("Ustaw folder &projektu…", self._cc_panel_set_project_folder)
        cc_panel_menu.addAction("&Edytuj listy dropdown…", self._cc_panel_show_settings)
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
        self._editor_panel = EditorPanel()
        self._history_panel = HistoryPanel()
        self._active_projects_panel = ActiveProjectsPanel()
        self._website_projects_panel = WebsiteProjectsPanel()
        self._hidden_projects_panel = HiddenProjectsPanel()
        self._simulator_panel = SimulatorPanel()
        self._projektant_panel = ProjectantPanel()
        self._cc_launcher_panel = CCLauncherPanel()
        self._zadania_panel = ZadaniaPanel()
        self._coa_panel = CoaPanel() if CoaPanel is not None else None
        self._iso_panel = IsoPanel() if IsoPanel is not None else None
        self._ingest_panel = IngestPanel() if IngestPanel is not None else None
        self._wiki_panel = WikiPanel() if WikiPanel is not None else None

        # Stacked widget — no tab bar, menu-driven navigation
        self._stack = QStackedWidget()
        self._stack.addWidget(self._editor_panel)             # 0 = Resources (full width)
        self._stack.addWidget(self._history_panel)            # 1 = Projects
        self._stack.addWidget(self._active_projects_panel)    # 2 = Active Projects
        self._stack.addWidget(self._website_projects_panel)   # 3 = Websites
        self._stack.addWidget(self._hidden_projects_panel)    # 4 = Hidden
        self._stack.addWidget(self._simulator_panel)          # 5 = Simulator
        self._stack.addWidget(self._projektant_panel)         # 6 = Projektant
        self._stack.addWidget(self._cc_launcher_panel)        # 7 = Sesje CC
        self._stack.addWidget(self._zadania_panel)             # 8 = Zadania

        # BB panels — track indices dynamically starting at 9
        bb_idx = 9
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

        # Connect signals
        self._projektant_panel.project_ready.connect(self._on_project_ready)
        self._history_panel.active_projects_changed.connect(self._active_projects_panel.refresh)
        self._history_panel.website_projects_changed.connect(self._website_projects_panel.refresh)
        self._history_panel.project_hidden.connect(self._hidden_projects_panel.refresh)
        self._hidden_projects_panel.project_unhidden.connect(self._history_panel.refresh)

    def _scan_resources(self) -> None:
        """Scan all resources and update status / welcome screen."""
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

    # --- cc-panel helpers ---

    _CC_TERMINAL_COLORS = ["#2dd4bf", "#fbbf24", "#a78bfa", "#fb7185"]  # teal/amber/purple/coral
    _CC_TERMINAL_NAMES = ["T1 — teal", "T2 — amber", "T3 — purple", "T4 — coral"]

    def _cc_panel_settings_path(self):
        from pathlib import Path
        return Path.home() / ".claude" / "cc-panel" / "ustawienia.json"

    def _cc_panel_load_settings(self) -> dict:
        import json
        p = self._cc_panel_settings_path()
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _cc_panel_save_settings(self, data: dict) -> None:
        import json
        p = self._cc_panel_settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _cc_panel_set_project_folder(self) -> None:
        from pathlib import Path as _Path
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QFrame
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor

        data = self._cc_panel_load_settings()
        # migrate legacy single projectPath
        paths: list[str] = data.get("projectPaths", ["", "", "", ""])
        if isinstance(paths, list):
            paths = (paths + ["", "", "", ""])[:4]
        else:
            paths = ["", "", "", ""]
        if not any(paths) and data.get("projectPath"):
            paths[0] = data["projectPath"]

        dlg = QDialog(self)
        dlg.setWindowTitle("cc-panel — foldery projektów")
        dlg.setMinimumWidth(580)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Wybierz folder projektu dla każdego terminala:"))

        path_labels: list[QLabel] = []

        def refresh_labels() -> None:
            for idx, lbl in enumerate(path_labels):
                lbl.setText(paths[idx] or "(nieustawiony)")
                lbl.setStyleSheet("color:#fff;" if paths[idx] else "color:#ccc;")

        def make_swap(idx_a: int, idx_b: int) -> callable:
            def swap():
                paths[idx_a], paths[idx_b] = paths[idx_b], paths[idx_a]
                refresh_labels()
            return swap

        for i, (name, color) in enumerate(zip(self._CC_TERMINAL_NAMES, self._CC_TERMINAL_COLORS)):
            row = QHBoxLayout()

            # swap buttons ↑↓
            up_btn = QPushButton("↑")
            up_btn.setFixedWidth(24)
            up_btn.setEnabled(i > 0)
            if i > 0:
                up_btn.clicked.connect(make_swap(i, i - 1))
            row.addWidget(up_btn)

            down_btn = QPushButton("↓")
            down_btn.setFixedWidth(24)
            down_btn.setEnabled(i < 3)
            if i < 3:
                down_btn.clicked.connect(make_swap(i, i + 1))
            row.addWidget(down_btn)

            badge = QLabel(f"  {name}  ")
            badge.setStyleSheet(
                f"background:{color}; color:#000; border-radius:4px; padding:2px 6px; font-weight:bold;"
            )
            badge.setFixedWidth(130)
            row.addWidget(badge)

            lbl = QLabel(paths[i] or "(nieustawiony)")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#fff;" if paths[i] else "color:#ccc;")
            path_labels.append(lbl)
            row.addWidget(lbl, 1)

            def make_picker(idx: int, lbl_ref: QLabel) -> callable:
                def pick():
                    start = paths[idx] if paths[idx] else str(_Path.home())
                    folder = QFileDialog.getExistingDirectory(dlg, f"Folder dla T{idx+1}", start)
                    if folder:
                        paths[idx] = folder
                        lbl_ref.setText(folder)
                        lbl_ref.setStyleSheet("color:#fff;")
                return pick

            btn = QPushButton("…")
            btn.setFixedWidth(30)
            btn.clicked.connect(make_picker(i, lbl))
            row.addWidget(btn)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)

            layout.addLayout(row)
            layout.addWidget(sep)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Zapisz")
        cancel_btn = QPushButton("Anuluj")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            data["projectPaths"] = paths
            data.pop("projectPath", None)  # usuń legacy
            self._cc_panel_save_settings(data)
            self._status_bar.set_status("cc-panel: foldery projektów zapisane")

    def _cc_panel_show_settings(self) -> None:
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
            QListWidget, QListWidgetItem, QPushButton, QInputDialog,
            QLabel, QDialogButtonBox, QAbstractItemView,
        )
        from PySide6.QtCore import Qt

        data = self._cc_panel_load_settings()
        slash: list[dict] = data.get("slashDropdown", [])
        user_cmds: list[dict] = data.get("userCommands", [])
        messages: list[dict] = data.get("messages", [])

        dlg = QDialog(self)
        dlg.setWindowTitle("cc-panel — edycja list dropdown")
        dlg.setMinimumSize(560, 440)
        root = QVBoxLayout(dlg)

        tabs = QTabWidget()
        root.addWidget(tabs)

        def make_list_widget(items: list[dict], fields: list[str]) -> tuple[QWidget, QListWidget]:
            """Build tab with list + add/edit/delete/up/down buttons."""
            w = QWidget()
            h = QHBoxLayout(w)
            lst = QListWidget()
            lst.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            for it in items:
                display = " | ".join(str(it.get(f, "")) for f in fields)
                li = QListWidgetItem(display)
                li.setData(Qt.ItemDataRole.UserRole, dict(it))
                lst.addItem(li)
            h.addWidget(lst, 1)

            btn_col = QVBoxLayout()
            btn_col.setAlignment(Qt.AlignmentFlag.AlignTop)

            def refresh_item(li: QListWidgetItem, it: dict) -> None:
                display = " | ".join(str(it.get(f, "")) for f in fields)
                li.setText(display)
                li.setData(Qt.ItemDataRole.UserRole, it)

            def add_item() -> None:
                values: dict = {}
                for field in fields:
                    label_map = {"label": "Etykieta w dropdown", "value": "Wartość (komenda)", "text": "Pełny tekst wiadomości"}
                    prompt = label_map.get(field, field)
                    val, ok = QInputDialog.getText(dlg, "Nowa pozycja", f"{prompt}:", text="")
                    if not ok:
                        return
                    values[field] = val
                display = " | ".join(str(values.get(f, "")) for f in fields)
                li = QListWidgetItem(display)
                li.setData(Qt.ItemDataRole.UserRole, values)
                lst.addItem(li)
                lst.setCurrentItem(li)

            def edit_item() -> None:
                li = lst.currentItem()
                if not li:
                    return
                it = dict(li.data(Qt.ItemDataRole.UserRole))
                for field in fields:
                    label_map = {"label": "Etykieta w dropdown", "value": "Wartość (komenda)", "text": "Pełny tekst wiadomości"}
                    prompt = label_map.get(field, field)
                    val, ok = QInputDialog.getText(dlg, "Edycja", f"{prompt}:", text=it.get(field, ""))
                    if not ok:
                        return
                    it[field] = val
                refresh_item(li, it)

            def delete_item() -> None:
                row = lst.currentRow()
                if row >= 0:
                    lst.takeItem(row)

            def move_up() -> None:
                row = lst.currentRow()
                if row > 0:
                    item = lst.takeItem(row)
                    lst.insertItem(row - 1, item)
                    lst.setCurrentRow(row - 1)

            def move_down() -> None:
                row = lst.currentRow()
                if row < lst.count() - 1:
                    item = lst.takeItem(row)
                    lst.insertItem(row + 1, item)
                    lst.setCurrentRow(row + 1)

            for label, fn in [("Dodaj", add_item), ("Edytuj", edit_item), ("Usuń", delete_item), ("↑ Wyżej", move_up), ("↓ Niżej", move_down)]:
                btn = QPushButton(label)
                btn.clicked.connect(fn)
                btn_col.addWidget(btn)

            h.addLayout(btn_col)
            return w, lst

        tab_slash, lst_slash = make_list_widget(slash, ["label", "value"])
        tabs.addTab(tab_slash, "Slash (/cmd)")

        tab_user, lst_user = make_list_widget(user_cmds, ["label", "value"])
        tabs.addTab(tab_user, "Komendy użytk.")

        tab_msg, lst_msg = make_list_widget(messages, ["label", "text"])
        tabs.addTab(tab_msg, "Wiadomości")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        root.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        def collect(lst_w: QListWidget) -> list[dict]:
            return [lst_w.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst_w.count())]

        data["slashDropdown"] = collect(lst_slash)
        data["userCommands"] = collect(lst_user)
        data["messages"] = collect(lst_msg)
        self._cc_panel_save_settings(data)
        self._status_bar.set_status("cc-panel: listy dropdown zapisane")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Claude Manager",
            "Claude Manager v0.2\n\n"
            "Centralna aplikacja zarządzająca wszystkimi narzędziami\n"
            "i zasobami Claude Code z jednego miejsca.",
        )
