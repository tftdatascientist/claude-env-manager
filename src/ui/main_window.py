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
from src.ui.status_bar import StatusBar


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
        view_menu.addAction("&History", lambda: self._tabs.setCurrentIndex(1), "Ctrl+2")

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction("&About", self._show_about)

    def _setup_ui(self) -> None:
        self._tree_panel = TreePanel()
        self._editor_panel = EditorPanel()
        self._history_panel = HistoryPanel()

        # Right side: tabs for editor and history
        self._tabs = QTabWidget()
        self._tabs.addTab(self._editor_panel, "Resources")
        self._tabs.addTab(self._history_panel, "History")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree_panel)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 900])

        self.setCentralWidget(splitter)

        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)

        # Connect signals
        self._tree_panel.resource_selected.connect(self._on_resource_selected)

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

    def _refresh_all(self) -> None:
        """Refresh resources and history."""
        self._scan_resources()
        self._history_panel.refresh()

    def _on_resource_selected(self, resource: Resource) -> None:
        """Handle resource selection from tree."""
        self._tabs.setCurrentIndex(0)
        self._editor_panel.show_resource(resource)
        self._status_bar.show_resource_info(resource)

    def _expand_all(self) -> None:
        self._tree_panel._tree.expandAll()

    def _collapse_all(self) -> None:
        self._tree_panel._tree.collapseAll()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Claude Environment Manager",
            "Claude Environment Manager v0.1\n\n"
            "Browse and view all local Claude Code\n"
            "and Claude.ai resources from one place.\n\n"
            "Phase 1: Scanner + TreeView + Read-only viewer",
        )
