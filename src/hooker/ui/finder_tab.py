"""Hook Finder — zakładka do wyszukiwania i przeglądania hooków CC."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.hooker.core.merger import merge, MergedHook
from src.hooker.core.model import HOOK_TYPE_INFO, HookLevel, HookType
from src.hooker.core.scanner import scan_empty_candidates, scan_global, scan_project


class FinderTab(QWidget):
    """Hook Finder — 3 sekcje (global / project / puste) + merge view."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._setup_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        self._btn_folder = QPushButton("📁 Wybierz folder projektu…")
        self._btn_folder.clicked.connect(self._pick_folder)
        self._lbl_project = QLabel("<i>Brak projektu — pokazuję tylko hooki globalne</i>")
        self._lbl_project.setStyleSheet("color:#94a3b8; font-size:11px;")
        self._btn_refresh = QPushButton("↺ Odśwież")
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_clear = QPushButton("✕ Wyczyść projekt")
        self._btn_clear.clicked.connect(self._clear_folder)
        toolbar.addWidget(self._btn_folder)
        toolbar.addWidget(self._lbl_project, 1)
        toolbar.addWidget(self._btn_clear)
        toolbar.addWidget(self._btn_refresh)
        root.addLayout(toolbar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#334155;")
        root.addWidget(sep)

        # Splitter: 3 sekcje | merge view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ---- Lewa strona: 3 sekcje ----
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(320)
        left_container = QWidget()
        self._left_layout = QVBoxLayout(left_container)
        self._left_layout.setContentsMargins(4, 4, 4, 4)
        self._left_layout.setSpacing(12)

        self._group_global = self._make_section("🌐 GLOBALNE", "#3b82f6")
        self._tree_global = self._make_hook_tree()
        self._group_global.layout().addWidget(self._tree_global)
        self._left_layout.addWidget(self._group_global)

        self._group_project = self._make_section("📁 PROJEKT", "#10b981")
        self._tree_project = self._make_hook_tree()
        self._group_project.layout().addWidget(self._tree_project)
        self._left_layout.addWidget(self._group_project)

        self._group_empty = self._make_section("○ PUSTE PLIKI", "#64748b")
        self._tree_empty = QTreeWidget()
        self._tree_empty.setHeaderLabels(["Plik (można dodać hooki)"])
        self._tree_empty.setAlternatingRowColors(True)
        self._group_empty.layout().addWidget(self._tree_empty)
        self._left_layout.addWidget(self._group_empty)

        self._left_layout.addStretch()
        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        # ---- Prawa strona: merge view ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        merge_header = QLabel("⊕ EFEKTYWNY MERGE (jak CC widzi hooki)")
        merge_header.setStyleSheet(
            "color:#cbd5e1; font-size:11px; font-weight:bold; padding:4px 0;"
        )
        right_layout.addWidget(merge_header)

        self._tree_merge = QTreeWidget()
        self._tree_merge.setHeaderLabels(["Typ / Źródło", "Matcher", "Command"])
        self._tree_merge.setAlternatingRowColors(True)
        self._tree_merge.setColumnWidth(0, 200)
        self._tree_merge.setColumnWidth(1, 140)
        right_layout.addWidget(self._tree_merge)

        splitter.addWidget(right)
        splitter.setSizes([400, 500])

        root.addWidget(splitter, 1)

    def _make_section(self, title: str, color: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setStyleSheet(
            f"QGroupBox {{ "
            f"font-weight:bold; color:{color}; "
            f"border:1px solid {color}44; border-radius:4px; "
            f"margin-top:8px; padding-top:4px;"
            f"}} "
            f"QGroupBox::title {{ subcontrol-origin: margin; left:8px; }}"
        )
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 8, 4, 4)
        return box

    def _make_hook_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(["Typ", "Matcher", "Command"])
        tree.setAlternatingRowColors(True)
        tree.setColumnWidth(0, 160)
        tree.setColumnWidth(1, 120)
        return tree

    # ------------------------------------------------------------------ Actions

    def _pick_folder(self) -> None:
        start = str(self._project_path) if self._project_path else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder projektu CC", start)
        if folder:
            self._project_path = Path(folder)
            self.refresh()

    def _clear_folder(self) -> None:
        self._project_path = None
        self.refresh()

    def refresh(self) -> None:
        """Odśwież wszystkie trzy sekcje i merge view."""
        global_hooks, global_path = scan_global()
        project_hooks: list = []
        if self._project_path:
            project_hooks, _ = scan_project(self._project_path)
            self._lbl_project.setText(
                f"<b style='color:#10b981'>{self._project_path.name}</b>"
                f"<span style='color:#64748b'> — {self._project_path}</span>"
            )
        else:
            self._lbl_project.setText(
                "<i style='color:#94a3b8'>Brak projektu — pokazuję tylko hooki globalne</i>"
            )

        # Nagłówki sekcji z licznikiem
        self._group_global.setTitle(
            f"🌐 GLOBALNE — {len(global_hooks)} hook{'i' if len(global_hooks) != 1 else ''}"
            f"  ({global_path})"
        )
        proj_count = len(project_hooks)
        proj_label = "Brak projektu" if not self._project_path else str(self._project_path)
        self._group_project.setTitle(
            f"📁 PROJEKT — {proj_count} hook{'i' if proj_count != 1 else ''}"
            f"  ({proj_label})"
        )

        # Populuj drzewa
        self._populate_hook_tree(self._tree_global, global_hooks)
        self._populate_hook_tree(self._tree_project, project_hooks)
        self._populate_empty(scan_empty_candidates(self._project_path))

        # Merge view
        result = merge(global_hooks, project_hooks)
        self._populate_merge_tree(result.merged)

    # ------------------------------------------------------------------ Tree builders

    def _populate_hook_tree(self, tree: QTreeWidget, hooks: list) -> None:
        tree.clear()
        by_type: dict[HookType, list] = {}
        for h in hooks:
            by_type.setdefault(h.hook_type, []).append(h)

        for hook_type in HookType:
            type_hooks = by_type.get(hook_type, [])
            if not type_hooks:
                continue
            info = HOOK_TYPE_INFO.get(hook_type, {})
            color = info.get("color", "#94a3b8")

            type_item = QTreeWidgetItem([hook_type.value, "", ""])
            type_item.setForeground(0, QColor(color))
            bold = QFont()
            bold.setBold(True)
            type_item.setFont(0, bold)
            type_item.setToolTip(0, self._hook_tooltip(hook_type))
            tree.addTopLevelItem(type_item)

            for h in type_hooks:
                child = QTreeWidgetItem([
                    "",
                    h.matcher or "(wszystkie)",
                    h.command,
                ])
                child.setForeground(0, QColor(color))
                child.setToolTip(2, h.command)
                type_item.addChild(child)

            type_item.setExpanded(True)

    def _populate_empty(self, paths: list[Path]) -> None:
        self._tree_empty.clear()
        count = len(paths)
        self._group_empty.setTitle(
            f"○ PUSTE PLIKI — {count} {'plik' if count == 1 else 'pliki/ów'} bez hooków"
        )
        for p in paths:
            item = QTreeWidgetItem([str(p)])
            item.setForeground(0, QColor("#64748b"))
            item.setToolTip(0, "Możesz dodać hooki do tego pliku przez Hook Setup")
            self._tree_empty.addTopLevelItem(item)

    def _populate_merge_tree(self, merged: list[MergedHook]) -> None:
        self._tree_merge.clear()

        by_type: dict[HookType, list[MergedHook]] = {}
        for m in merged:
            by_type.setdefault(m.hook.hook_type, []).append(m)

        for hook_type in HookType:
            items = by_type.get(hook_type, [])
            if not items:
                continue
            info = HOOK_TYPE_INFO.get(hook_type, {})
            color = info.get("color", "#94a3b8")

            type_item = QTreeWidgetItem([hook_type.value, "", ""])
            type_item.setForeground(0, QColor(color))
            bold = QFont()
            bold.setBold(True)
            type_item.setFont(0, bold)
            type_item.setToolTip(0, self._hook_tooltip(hook_type))
            self._tree_merge.addTopLevelItem(type_item)

            for m in items:
                source = "🌐" if m.hook.level == HookLevel.GLOBAL else "📁"
                shadow_marker = " ⚠️" if m.is_shadowed else ""
                label = f"{source} {m.source_label}{shadow_marker}"

                child = QTreeWidgetItem([
                    label,
                    m.hook.matcher or "(wszystkie)",
                    m.hook.command,
                ])
                child.setForeground(0, QColor(color))
                child.setToolTip(2, m.hook.command)
                if m.is_shadowed:
                    child.setToolTip(0,
                        f"Ten hook nakłada się z {len(m.shadowed_by)} hookiem/ami na innym poziomie.\n"
                        "CC uruchamia oba — to informacja wizualna, nie błąd.")
                type_item.addChild(child)

            type_item.setExpanded(True)

    @staticmethod
    def _hook_tooltip(hook_type: HookType) -> str:
        info = HOOK_TYPE_INFO.get(hook_type, {})
        parts = []
        if info.get("when"):
            parts.append(f"Kiedy: {info['when']}")
        if info.get("input"):
            parts.append(f"Input: {info['input']}")
        if info.get("output"):
            parts.append(f"Output: {info['output']}")
        return "\n".join(parts)
