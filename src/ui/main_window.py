"""Main application window with tree, editor, history, and status bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QMessageBox, QTabWidget,
)

from src.models.resource import Resource
from src.scanner.discovery import discover_all
from src.scanner.indexer import build_tree
from src.ui.tree_panel import TreePanel
from src.ui.editor_panel import EditorPanel
from src.ui.history_panel import HistoryPanel
from src.ui.active_projects_panel import ActiveProjectsPanel
from src.ui.website_projects_panel import WebsiteProjectsPanel
from src.ui.hidden_projects_panel import HiddenProjectsPanel
from src.ui.status_bar import StatusBar
from src.ui.simulator.simulator_panel import SimulatorPanel
from src.ui.projektant_panel import ProjectantPanel

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


class MainWindow(QMainWindow):
    """Main window: tree panel (left) + tabbed content (right) + status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Claude Environment Manager")
        self.setMinimumSize(1000, 600)
        self.resize(1400, 800)

        self._setup_menu()
        self._setup_ui()
        self._scan_resources()
        self._czy_dialog = None
        if show_startup_factoid is not None:
            try:
                self._czy_dialog = show_startup_factoid(parent=self)
            except Exception as _czy_exc:
                print(f"[CZY] start widget failed: {_czy_exc}", file=_sys.stderr)

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction("&Refresh", self._refresh_all, "F5")
        file_menu.addSeparator()
        file_menu.addAction("&Quit", self.close, "Ctrl+Q")

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction("Expand &All", self._expand_all)
        view_menu.addAction("&Collapse All", self._collapse_all)
        view_menu.addSeparator()
        view_menu.addAction("&Resources", lambda: self._tabs.setCurrentIndex(0), "Ctrl+1")
        view_menu.addAction("&Projects", lambda: self._tabs.setCurrentIndex(1), "Ctrl+2")
        view_menu.addAction("&Active Projects", lambda: self._tabs.setCurrentIndex(2), "Ctrl+3")
        view_menu.addAction("&Websites", lambda: self._tabs.setCurrentIndex(3), "Ctrl+4")
        view_menu.addAction("&Hidden", lambda: self._tabs.setCurrentIndex(4), "Ctrl+5")
        view_menu.addAction("&Simulator", lambda: self._tabs.setCurrentIndex(5), "Ctrl+6")
        view_menu.addAction("Pro&jektant", lambda: self._tabs.setCurrentIndex(6), "Ctrl+7")
        if CoaPanel is not None:
            view_menu.addAction("CO&A (BB)", lambda: self._tabs.setCurrentIndex(7), "Ctrl+8")
        if IsoPanel is not None:
            view_menu.addAction("&ISO (BB)", lambda: self._tabs.setCurrentIndex(8), "Ctrl+9")
        if show_startup_factoid is not None:
            view_menu.addAction("CZ&Y wiesz że…", self._show_czy_factoid)
        view_menu.addSeparator()
        view_menu.addAction("Reset category &colors", self._reset_colors)

        tools_menu = menu_bar.addMenu("&Tools")
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
        self._coa_panel = CoaPanel() if CoaPanel is not None else None
        self._iso_panel = IsoPanel() if IsoPanel is not None else None

        # Right side: tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._editor_panel, "Resources")
        self._tabs.addTab(self._history_panel, "Projects")
        self._tabs.addTab(self._active_projects_panel, "Active Projects")
        self._tabs.addTab(self._website_projects_panel, "Websites")
        self._tabs.addTab(self._hidden_projects_panel, "Hidden")
        self._tabs.addTab(self._simulator_panel, "Simulator")
        self._tabs.addTab(self._projektant_panel, "Projektant")
        if self._coa_panel is not None:
            self._tabs.addTab(self._coa_panel, "COA (BB)")
        if self._iso_panel is not None:
            self._tabs.addTab(self._iso_panel, "ISO (BB)")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree_panel)
        splitter.addWidget(self._tabs)
        splitter.setSizes([300, 1100])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        self._tree_panel.setMinimumWidth(150)
        self._tabs.setMinimumWidth(400)

        self.setCentralWidget(splitter)

        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)

        # Connect signals
        self._tree_panel.resource_selected.connect(self._on_resource_selected)
        self._tree_panel.project_detail_requested.connect(self._on_project_detail)
        self._tree_panel.refresh_requested.connect(self._scan_resources)
        self._history_panel.active_projects_changed.connect(self._active_projects_panel.refresh)
        self._history_panel.website_projects_changed.connect(self._website_projects_panel.refresh)
        self._history_panel.project_hidden.connect(self._hidden_projects_panel.refresh)
        self._hidden_projects_panel.project_unhidden.connect(self._history_panel.refresh)

    def _scan_resources(self) -> None:
        """Scan all resources and populate the tree."""
        self._status_bar.set_status("Scanning resources...")

        managed, user, projects, external = discover_all()

        tree = build_tree(managed, user, projects, external)
        self._tree_panel.populate(tree)

        total = (
            len(managed)
            + len(user)
            + sum(len(p.resources) for p in projects)
            + len(external)
        )
        self._status_bar.set_status("Ready")
        self._status_bar.show_scan_summary(total)

        # Show welcome screen only if no resource is currently selected
        if self._editor_panel._current_resource is None:
            self._editor_panel.show_welcome(
                managed=len(managed),
                user=len(user),
                projects=len(projects),
                external=len(external),
            )

    def _refresh_all(self) -> None:
        """Refresh resources, history, active projects, and websites."""
        self._scan_resources()
        self._history_panel.refresh()
        self._active_projects_panel.refresh()
        self._website_projects_panel.refresh()
        self._hidden_projects_panel.refresh()

    def _on_resource_selected(self, resource: Resource) -> None:
        """Handle resource selection from tree."""
        self._tabs.setCurrentIndex(0)
        self._editor_panel.show_resource(resource)
        self._status_bar.show_resource_info(resource)

    def _on_project_detail(self, proj: dict) -> None:
        """Handle project selection from All Projects list."""
        self._tabs.setCurrentIndex(0)
        self._editor_panel.show_project_detail(proj)

    def _expand_all(self) -> None:
        self._tree_panel._tree.expandAll()

    def _collapse_all(self) -> None:
        self._tree_panel._tree.collapseAll()

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
            "About Claude Environment Manager",
            "Claude Environment Manager v0.1\n\n"
            "Browse and view all local Claude Code\n"
            "and Claude.ai resources from one place.\n\n"
            "Phase 1: Scanner + TreeView + Read-only viewer",
        )
