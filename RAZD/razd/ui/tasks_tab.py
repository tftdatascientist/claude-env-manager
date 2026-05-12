from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from razd.db.repository import RazdRepository
    from razd.notion.tasks_fetcher import NotionTasksFetcher, NotionTask

logger = logging.getLogger(__name__)

_SLOT_COLORS = ["#7C3AED", "#0EA5E9", "#10B981", "#F59E0B"]

_STATUS_COLUMNS = ["Not started", "In progress", "Done"]
_STATUS_LABELS  = ["Do zrobienia", "W trakcie", "Gotowe"]

_STATUS_STYLE = {
    "Not started": {"color": "#aaa",    "bg": "#252525", "border": "#444"},
    "In progress": {"color": "#fff",    "bg": "#0a2a3a", "border": "#0EA5E9"},
    "Done":        {"color": "#fff",    "bg": "#0a2a1a", "border": "#10B981"},
}

_DONE_STATUSES = {"Done", "Cancel"}

# Tryby filtrowania — jakie statusy są widoczne
_FILTER_MODES: list[tuple[str, set[str]]] = [
    ("Wszystkie",         {"Not started", "In progress", "Done", "Cancel"}),
    ("Do zrobienia",      {"Not started"}),
    ("W trakcie",         {"In progress"}),
    ("Do zrobienia + W trakcie", {"Not started", "In progress"}),
    ("Gotowe",            {"Done", "Cancel"}),
]


# ──────────────────────────────────────────────────────────────────────────────
# Wątki robocze
# ──────────────────────────────────────────────────────────────────────────────

class _FetchThread(QThread):
    done = Signal(list, str)
    error = Signal(str)

    def __init__(self, fetcher, project_page_id: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._project_page_id = project_page_id

    def run(self) -> None:
        try:
            tasks = self._fetcher.fetch_tasks(project_page_ids=[self._project_page_id])
            self.done.emit(tasks, self._project_page_id)
        except Exception as exc:
            self.error.emit(str(exc))


class _CreateThread(QThread):
    done = Signal(object)
    error = Signal(str)

    def __init__(self, fetcher, title: str, project_page_id: str,
                 deadline: str | None, details: str | None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._title = title
        self._project_page_id = project_page_id
        self._deadline = deadline
        self._details = details

    def run(self) -> None:
        try:
            task = self._fetcher.create_task(
                title=self._title,
                project_page_id=self._project_page_id,
                deadline=self._deadline,
                details=self._details,
            )
            self.done.emit(task)
        except Exception as exc:
            self.error.emit(str(exc))


class _StatusThread(QThread):
    done = Signal(str, str)
    error = Signal(str)

    def __init__(self, fetcher, page_id: str, new_status: str,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._page_id = page_id
        self._new_status = new_status

    def run(self) -> None:
        try:
            ok = self._fetcher.update_status(self._page_id, self._new_status)
            if ok:
                self.done.emit(self._page_id, self._new_status)
            else:
                self.error.emit("Błąd aktualizacji statusu")
        except Exception as exc:
            self.error.emit(str(exc))


class _UpdateThread(QThread):
    done = Signal(str)   # page_id
    error = Signal(str)

    def __init__(self, fetcher, page_id: str,
                 title: str | None, deadline: str | None, details: str | None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._page_id = page_id
        self._title = title
        self._deadline = deadline
        self._details = details

    def run(self) -> None:
        try:
            ok = self._fetcher.update_task(
                self._page_id,
                title=self._title,
                deadline=self._deadline,
                details=self._details,
            )
            if ok:
                self.done.emit(self._page_id)
            else:
                self.error.emit("Błąd aktualizacji zadania")
        except Exception as exc:
            self.error.emit(str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Karta zadania
# ──────────────────────────────────────────────────────────────────────────────

class _TaskCard(QFrame):
    status_change_requested = Signal(str, str)
    edit_requested = Signal(dict)   # task dict

    def __init__(self, task: dict, project_color: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self._color = project_color
        self._build()

    def _build(self) -> None:
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(46)
        self.setStyleSheet(
            f"QFrame {{ background: #1e1e1e; border: 1px solid #2a2a2a;"
            f" border-left: 3px solid {self._color}; border-radius: 4px; }}"
            f"QFrame:hover {{ background: #252525; border-color: #383838;"
            f" border-left: 3px solid {self._color}; }}"
        )
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(1)

        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_lbl = QLabel(self._task["title"])
        title_lbl.setStyleSheet(
            "color: #e0e0e0; font-size: 11px; font-weight: bold; background: transparent;"
        )
        title_lbl.setWordWrap(False)
        # obetnij tytuł elipsą jeśli za długi
        from PySide6.QtCore import Qt as _Qt
        title_lbl.setSizePolicy(
            title_lbl.sizePolicy().horizontalPolicy(),
            title_lbl.sizePolicy().verticalPolicy(),
        )
        title_row.addWidget(title_lbl, 1)

        edit_hint = QLabel("✎")
        edit_hint.setStyleSheet("color: #3a3a3a; font-size: 10px; background: transparent;")
        edit_hint.setToolTip("Kliknij aby edytować")
        title_row.addWidget(edit_hint)
        layout.addLayout(title_row)

        meta_parts = []
        if self._task.get("deadline"):
            meta_parts.append(f"do {self._task['deadline']}")
        if self._task.get("details"):
            snippet = self._task["details"][:35].replace("\n", " ")
            meta_parts.append(snippet + ("…" if len(self._task["details"]) > 35 else ""))
        if self._task.get("dirty"):
            meta_parts.append("⏳")
        meta_lbl = QLabel("  ·  ".join(meta_parts) if meta_parts else "")
        meta_lbl.setStyleSheet("color: #555; font-size: 9px; background: transparent;")
        layout.addWidget(meta_lbl)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.edit_requested.emit(self._task)
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e1e; border: 1px solid #333; color: #ccc; font-size: 11px; }"
            "QMenu::item:selected { background: #2a3a4a; }"
        )
        current = self._task["status"]
        for status in ["Not started", "In progress", "Done", "Cancel"]:
            if status != current:
                label = {
                    "Not started": "→ Do zrobienia",
                    "In progress": "→ W trakcie",
                    "Done": "→ Gotowe",
                    "Cancel": "→ Anuluj",
                }[status]
                act = menu.addAction(label)
                act.triggered.connect(lambda checked=False, s=status: self._request_status(s))
        menu.exec(pos)

    def _request_status(self, new_status: str) -> None:
        self.status_change_requested.emit(self._task["notion_page_id"], new_status)


# ──────────────────────────────────────────────────────────────────────────────
# Kolumna kanban
# ──────────────────────────────────────────────────────────────────────────────

class _KanbanColumn(QWidget):
    status_change_requested = Signal(str, str)
    edit_requested = Signal(dict)

    def __init__(self, status: str, label: str,
                 project_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._project_color = project_color
        self._cards: list[_TaskCard] = []

        style = _STATUS_STYLE.get(status, {"color": "#aaa", "bg": "#1a1a1a", "border": "#333"})
        col = style["color"]
        bg  = style["bg"]
        brd = style["border"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QFrame()
        header.setFixedHeight(30)
        header.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 4px; border: 1px solid {brd}; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_lbl = QLabel(label)
        h_lbl.setStyleSheet(f"color: {col}; font-size: 10px; font-weight: bold; background: transparent;")
        self._count_lbl = QLabel("0")
        self._count_lbl.setStyleSheet(
            f"color: {col}; font-size: 10px; font-weight: bold; background: transparent;"
        )
        self._h_lbl = h_lbl
        h_layout.addWidget(h_lbl)
        h_layout.addStretch()
        h_layout.addWidget(self._count_lbl)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._inner = QWidget()
        self._inner.setStyleSheet("QWidget { background: transparent; }")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(4)
        self._inner_layout.addStretch()
        scroll.setWidget(self._inner)
        layout.addWidget(scroll, 1)

    def set_tasks(self, tasks: list[dict]) -> None:
        for card in self._cards:
            self._inner_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for task in tasks:
            card = _TaskCard(task, self._project_color)
            card.status_change_requested.connect(self.status_change_requested)
            card.edit_requested.connect(self.edit_requested)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, card)
            self._cards.append(card)

        self._count_lbl.setText(str(len(tasks)))

    def set_header(self, text: str) -> None:
        self._h_lbl.setText(text)


# ──────────────────────────────────────────────────────────────────────────────
# Panel jednego projektu
# ──────────────────────────────────────────────────────────────────────────────

class _ProjectKanban(QWidget):
    status_change_requested = Signal(str, str)
    task_create_requested = Signal(str, str, str, str)
    edit_requested = Signal(dict)

    def __init__(self, project_page_id: str, project_name: str,
                 color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_page_id = project_page_id
        self._color = color
        self._columns: dict[str, _KanbanColumn] = {}
        self._all_tasks: list[dict] = []
        self._active_filter: set[str] = set(_FILTER_MODES[0][1])
        self._build(project_name)

    def _build(self, project_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── pasek projektu ────────────────────────────────────────────────────
        top_frame = QFrame()
        top_frame.setStyleSheet(
            f"QFrame {{ background: #1a1a1a; border-radius: 5px;"
            f" border: 1px solid {self._color}44; }}"
        )
        top = QHBoxLayout(top_frame)
        top.setContentsMargins(10, 5, 10, 5)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self._color}; font-size: 14px; background: transparent;")
        top.addWidget(dot)

        name_lbl = QLabel(project_name)
        name_lbl.setStyleSheet(
            "color: #e8e8e8; font-size: 12px; font-weight: bold; background: transparent;"
        )
        top.addWidget(name_lbl)
        top.addStretch()

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #555; font-size: 9px; background: transparent;")
        top.addWidget(self._status_lbl)

        btn_add = QPushButton("+ Zadanie")
        btn_add.setFixedHeight(24)
        btn_add.setStyleSheet(
            f"QPushButton {{ color: #fff; font-size: 10px; font-weight: bold; padding: 0 10px;"
            f" background: {self._color}; border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background: {self._color}cc; }}"
        )
        btn_add.clicked.connect(self._on_add)
        top.addWidget(btn_add)
        layout.addWidget(top_frame)

        # ── pasek filtrów ─────────────────────────────────────────────────────
        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            "QFrame { background: #161616; border-radius: 4px; border: 1px solid #282828; }"
        )
        filter_row = QHBoxLayout(filter_frame)
        filter_row.setContentsMargins(6, 3, 6, 3)
        filter_row.setSpacing(4)

        filter_lbl = QLabel("Filtr:")
        filter_lbl.setStyleSheet("color: #555; font-size: 9px; background: transparent;")
        filter_row.addWidget(filter_lbl)

        self._filter_btns: list[QPushButton] = []
        for i, (label, statuses) in enumerate(_FILTER_MODES):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setFixedHeight(20)
            btn.setStyleSheet(self._filter_btn_style(active=(i == 0)))
            btn.clicked.connect(lambda checked=False, idx=i: self._apply_filter(idx))
            filter_row.addWidget(btn)
            self._filter_btns.append(btn)

        filter_row.addStretch()
        layout.addWidget(filter_frame)

        # ── 3 kolumny kanban — splitter umożliwia ręczne regulowanie szerokości
        self._cols_splitter = QSplitter(Qt.Horizontal)
        self._cols_splitter.setHandleWidth(4)
        self._cols_splitter.setStyleSheet(
            "QSplitter::handle { background: #2a2a2a; border-radius: 2px; }"
            "QSplitter::handle:hover { background: #444; }"
        )
        for status, label in zip(_STATUS_COLUMNS, _STATUS_LABELS):
            col = _KanbanColumn(status, label, self._color)
            col.status_change_requested.connect(self.status_change_requested)
            col.edit_requested.connect(self.edit_requested)
            self._columns[status] = col
            self._cols_splitter.addWidget(col)
        layout.addWidget(self._cols_splitter, 1)

    def _filter_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {self._color}; color: #fff;"
                f" font-size: 9px; font-weight: bold; padding: 0 8px;"
                f" border: none; border-radius: 3px; }}"
                f"QPushButton:hover {{ background: {self._color}cc; }}"
            )
        return (
            "QPushButton { background: #222; color: #777; font-size: 9px;"
            " padding: 0 8px; border: 1px solid #333; border-radius: 3px; }"
            "QPushButton:hover { background: #2a2a2a; color: #aaa; }"
        )

    def _apply_filter(self, idx: int) -> None:
        _, statuses = _FILTER_MODES[idx]
        self._active_filter = set(statuses)
        for i, btn in enumerate(self._filter_btns):
            btn.setChecked(i == idx)
            btn.setStyleSheet(self._filter_btn_style(active=(i == idx)))
        self._render_tasks()

    def set_tasks(self, tasks: list[dict]) -> None:
        self._all_tasks = tasks
        self._render_tasks()

    def _render_tasks(self) -> None:
        # Zbierz przefiltrowane zadania per canonical status
        buckets: dict[str, list[dict]] = {s: [] for s in _STATUS_COLUMNS}
        for t in self._all_tasks:
            s = t["status"]
            canonical = "Done" if s in _DONE_STATUSES else s
            if canonical not in self._active_filter and s not in self._active_filter:
                continue
            buckets[canonical if canonical in buckets else "Not started"].append(t)

        # Które canonical kolumny mają jakiekolwiek zadania w aktywnym filtrze
        visible_statuses = [s for s in _STATUS_COLUMNS
                            if s in self._active_filter or
                            (s == "Done" and bool(self._active_filter & _DONE_STATUSES))]

        if len(visible_statuses) == 1:
            # Tryb rozszerzony: jeden status rozrzucony na 3 równe kolumny
            tasks = buckets[visible_statuses[0]]
            n = len(tasks)
            k = (n + 2) // 3
            chunks = [tasks[i * k: (i + 1) * k] for i in range(3)]
            label_map = {"Not started": "Do zrobienia", "In progress": "W trakcie", "Done": "Gotowe"}
            base_label = label_map.get(visible_statuses[0], visible_statuses[0])
            cols = list(self._columns.values())
            for i, col in enumerate(cols):
                col.set_tasks(chunks[i])
                if n > 0:
                    start, end = i * k + 1, min((i + 1) * k, n)
                    col.set_header(f"{base_label} {start}–{end}")
                else:
                    col.set_header(base_label)
                col.setVisible(True)
        else:
            # Tryb normalny: każda kolumna = swój status
            label_map = dict(zip(_STATUS_COLUMNS, _STATUS_LABELS))
            for status, col in self._columns.items():
                col.set_tasks(buckets[status])
                col.set_header(label_map[status])
                col.setVisible(True)

        # przywróć równe szerokości kolumn po każdej zmianie filtra
        total = self._cols_splitter.width()
        if total > 0:
            each = total // 3
            self._cols_splitter.setSizes([each, each, total - 2 * each])

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # wyrównaj kolumny przy pierwszym pokazaniu
        total = self._cols_splitter.width()
        if total > 10 and self._cols_splitter.sizes() == [0, 0, 0]:
            each = total // 3
            self._cols_splitter.setSizes([each, each, total - 2 * each])

    def set_status(self, text: str, ok: bool = True) -> None:
        self._status_lbl.setText(text)
        color = "#555" if ok else "#c55"
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 9px; background: transparent;")

    def _on_add(self) -> None:
        dlg = _NewTaskDialog(self._color, self)
        if dlg.exec() == QDialog.Accepted:
            self.task_create_requested.emit(
                self._project_page_id,
                dlg.title(),
                dlg.deadline(),
                dlg.details(),
            )


# ──────────────────────────────────────────────────────────────────────────────
# Dialog nowego zadania
# ──────────────────────────────────────────────────────────────────────────────

_INPUT_STYLE = (
    "QLineEdit, QTextEdit { background: #1e1e1e; border: 1px solid #333;"
    " border-radius: 4px; padding: 4px 8px; color: #ddd; font-size: 11px; }"
)
_LABEL_STYLE = "QLabel { color: #aaa; font-size: 11px; }"


class _NewTaskDialog(QDialog):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nowe zadanie")
        self.setMinimumWidth(380)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet("QDialog { background: #181818; }")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        lbl1 = QLabel("Tytuł zadania:")
        lbl1.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(lbl1)
        self._title = QLineEdit()
        self._title.setStyleSheet(_INPUT_STYLE)
        self._title.setPlaceholderText("Tytuł...")
        layout.addWidget(self._title)

        lbl2 = QLabel("Deadline (YYYY-MM-DD, opcjonalnie):")
        lbl2.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(lbl2)
        self._deadline = QLineEdit()
        self._deadline.setStyleSheet(_INPUT_STYLE)
        self._deadline.setPlaceholderText("np. 2026-06-01")
        layout.addWidget(self._deadline)

        lbl3 = QLabel("Szczegóły (opcjonalnie):")
        lbl3.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(lbl3)
        self._details = QTextEdit()
        self._details.setStyleSheet(_INPUT_STYLE)
        self._details.setFixedHeight(70)
        layout.addWidget(self._details)

        btns = QDialogButtonBox()
        ok = btns.addButton("Utwórz", QDialogButtonBox.AcceptRole)
        ok.setStyleSheet(
            f"QPushButton {{ background: {color}; color: #fff; font-weight: bold;"
            f" padding: 5px 18px; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background: {color}cc; }}"
        )
        cancel = btns.addButton("Anuluj", QDialogButtonBox.RejectRole)
        cancel.setStyleSheet(
            "QPushButton { color: #888; padding: 5px 12px; background: #222;"
            " border: 1px solid #333; border-radius: 4px; }"
            "QPushButton:hover { background: #2a2a2a; }"
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def title(self) -> str:
        return self._title.text().strip()

    def deadline(self) -> str:
        return self._deadline.text().strip()

    def details(self) -> str:
        return self._details.toPlainText().strip()

    def accept(self) -> None:
        if not self._title.text().strip():
            self._title.setStyleSheet(
                "QLineEdit { background: #1e1e1e; border: 1px solid #c55;"
                " border-radius: 4px; padding: 4px 8px; color: #ddd; font-size: 11px; }"
            )
            return
        super().accept()


# ──────────────────────────────────────────────────────────────────────────────
# Dialog edycji zadania
# ──────────────────────────────────────────────────────────────────────────────

class _EditTaskDialog(QDialog):
    def __init__(self, task: dict, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self.setWindowTitle("Edytuj zadanie")
        self.setMinimumWidth(400)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet("QDialog { background: #181818; }")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # nagłówek z aktualnym statusem
        status_label = {
            "Not started": "Do zrobienia",
            "In progress": "W trakcie",
            "Done": "Gotowe",
            "Cancel": "Anulowane",
        }.get(task.get("status", ""), task.get("status", ""))
        status_info = QLabel(f"Status: {status_label}")
        status_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(status_info)

        lbl1 = QLabel("Tytuł zadania:")
        lbl1.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(lbl1)
        self._title = QLineEdit(task.get("title", ""))
        self._title.setStyleSheet(_INPUT_STYLE)
        layout.addWidget(self._title)

        lbl2 = QLabel("Deadline (YYYY-MM-DD, puste = usuń):")
        lbl2.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(lbl2)
        self._deadline = QLineEdit(task.get("deadline") or "")
        self._deadline.setStyleSheet(_INPUT_STYLE)
        self._deadline.setPlaceholderText("np. 2026-06-01")
        layout.addWidget(self._deadline)

        lbl3 = QLabel("Szczegóły:")
        lbl3.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(lbl3)
        self._details = QTextEdit()
        self._details.setStyleSheet(_INPUT_STYLE)
        self._details.setFixedHeight(100)
        self._details.setPlainText(task.get("details") or "")
        layout.addWidget(self._details)

        btns = QDialogButtonBox()
        ok = btns.addButton("Zapisz", QDialogButtonBox.AcceptRole)
        ok.setStyleSheet(
            f"QPushButton {{ background: {color}; color: #fff; font-weight: bold;"
            f" padding: 5px 18px; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background: {color}cc; }}"
        )
        cancel = btns.addButton("Anuluj", QDialogButtonBox.RejectRole)
        cancel.setStyleSheet(
            "QPushButton { color: #888; padding: 5px 12px; background: #222;"
            " border: 1px solid #333; border-radius: 4px; }"
            "QPushButton:hover { background: #2a2a2a; }"
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def title(self) -> str:
        return self._title.text().strip()

    def deadline(self) -> str | None:
        v = self._deadline.text().strip()
        return v if v else None

    def details(self) -> str | None:
        v = self._details.toPlainText().strip()
        return v if v else None

    def accept(self) -> None:
        if not self._title.text().strip():
            self._title.setStyleSheet(
                "QLineEdit { background: #1e1e1e; border: 1px solid #c55;"
                " border-radius: 4px; padding: 4px 8px; color: #ddd; font-size: 11px; }"
            )
            return
        super().accept()

    def has_changes(self) -> bool:
        return (
            self.title() != self._task.get("title", "")
            or self.deadline() != (self._task.get("deadline") or None)
            or self.details() != (self._task.get("details") or None)
        )


# ──────────────────────────────────────────────────────────────────────────────
# Główna zakładka Zadania
# ──────────────────────────────────────────────────────────────────────────────

class RazdTasksTab(QWidget):
    def __init__(self, repo: RazdRepository, fetcher=None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._fetcher: NotionTasksFetcher | None = fetcher
        self._kanbans: dict[str, _ProjectKanban] = {}
        self._fetch_threads: list[_FetchThread] = []
        self._action_threads: list[QThread] = []

        self._build_ui()
        self._load_pinned()

        self._auto_sync = QTimer(self)
        self._auto_sync.timeout.connect(self.sync_all)
        self._auto_sync.start(5 * 60 * 1000)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(6, 6, 6, 6)

        top = QHBoxLayout()
        title = QLabel("Zadania")
        title.setStyleSheet("color: #ddd; font-weight: bold; font-size: 14px;")
        top.addWidget(title)
        top.addStretch()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #555; font-size: 10px;")
        top.addWidget(self._status_lbl)
        btn_sync = QPushButton("↻ Synchronizuj")
        btn_sync.setFixedHeight(24)
        btn_sync.setStyleSheet(
            "QPushButton { font-size: 10px; padding: 0 10px; background: #222;"
            " border: 1px solid #444; border-radius: 4px; color: #ccc; }"
            "QPushButton:hover { background: #2a2a2a; }"
        )
        btn_sync.clicked.connect(self.sync_all)
        top.addWidget(btn_sync)
        root.addLayout(top)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: transparent; }"
            "QTabBar::tab { background: #1a1a1a; color: #666; padding: 5px 14px;"
            " border: 1px solid #222; border-bottom: none; border-radius: 4px 4px 0 0;"
            " font-size: 11px; margin-right: 2px; }"
            "QTabBar::tab:selected { color: #ddd; background: #222; border-color: #333; }"
            "QTabBar::tab:hover { color: #aaa; background: #1e1e1e; }"
        )
        root.addWidget(self._tabs, 1)

        self._no_projects_lbl = QLabel(
            "Brak przypiętych projektów.\n"
            "Przejdź do zakładki Projekty i przypisz projekty do slotów."
        )
        self._no_projects_lbl.setAlignment(Qt.AlignCenter)
        self._no_projects_lbl.setStyleSheet("color: #555; font-size: 12px;")
        root.addWidget(self._no_projects_lbl)

    # ── ładowanie pinnowanych projektów ──────────────────────────────────────

    def _load_pinned(self) -> None:
        pinned = self._repo.get_pinned_projects()
        self._tabs.clear()
        self._kanbans.clear()

        if not pinned:
            self._tabs.hide()
            self._no_projects_lbl.show()
            return

        self._no_projects_lbl.hide()
        self._tabs.show()

        for slot, proj, color in pinned:
            kanban = _ProjectKanban(
                project_page_id=proj.notion_page_id,
                project_name=proj.name,
                color=color,
            )
            kanban.status_change_requested.connect(self._on_status_change)
            kanban.task_create_requested.connect(self._on_create_task)
            kanban.edit_requested.connect(self._on_edit_task)
            self._kanbans[proj.notion_page_id] = kanban
            self._tabs.addTab(kanban, proj.name)

        self._load_all_from_db()

    # ── ładowanie z lokalnej bazy ─────────────────────────────────────────────

    def _load_all_from_db(self) -> None:
        for page_id in self._kanbans:
            self._load_tasks_from_db(page_id)

    def _load_tasks_from_db(self, project_page_id: str) -> None:
        tasks = self._repo.list_tasks_for_project(project_page_id)
        kanban = self._kanbans.get(project_page_id)
        if kanban:
            kanban.set_tasks(tasks)

    # ── synchronizacja z Notion ───────────────────────────────────────────────

    def sync_all(self) -> None:
        if not self._fetcher or not self._fetcher.is_configured():
            self._status_lbl.setText("Notion tasks nie skonfigurowany")
            return
        self._status_lbl.setText("Synchronizuję...")
        for page_id in list(self._kanbans.keys()):
            self._fetch_project(page_id)

    def _fetch_project(self, project_page_id: str) -> None:
        thread = _FetchThread(self._fetcher, project_page_id, self)
        thread.done.connect(self._on_fetched)
        thread.error.connect(lambda msg: self._status_lbl.setText(f"Błąd: {msg[:60]}"))
        thread.start()
        self._fetch_threads.append(thread)

    def _on_fetched(self, tasks: list, project_page_id: str) -> None:
        for t in tasks:
            proj_pid = project_page_id if project_page_id in t.project_page_ids else (
                t.project_page_ids[0] if t.project_page_ids else project_page_id
            )
            self._repo.upsert_task(
                notion_page_id=t.page_id,
                title=t.title,
                status=t.status,
                deadline=t.deadline,
                details=t.details,
                project_page_id=proj_pid,
            )
        self._load_tasks_from_db(project_page_id)
        kanban = self._kanbans.get(project_page_id)
        if kanban:
            kanban.set_status(f"sync {len(tasks)} zadań")
        total = sum(len(self._repo.list_tasks_for_project(p)) for p in self._kanbans)
        self._status_lbl.setText(f"Zsynchronizowano {total} zadań")

    # ── zmiana statusu ────────────────────────────────────────────────────────

    def _on_status_change(self, page_id: str, new_status: str) -> None:
        self._repo.update_task_status_local(page_id, new_status)
        self._refresh_kanban_for_task(page_id)

        if self._fetcher and self._fetcher.is_configured():
            thread = _StatusThread(self._fetcher, page_id, new_status, self)
            thread.done.connect(self._on_status_synced)
            thread.error.connect(lambda msg: logger.error("status sync error: %s", msg))
            thread.start()
            self._action_threads.append(thread)

    def _on_status_synced(self, page_id: str, new_status: str) -> None:
        self._repo.mark_task_clean(page_id)
        self._refresh_kanban_for_task(page_id)

    # ── edycja zadania ────────────────────────────────────────────────────────

    def _on_edit_task(self, task: dict) -> None:
        # znajdź kolor projektu dla aktualnie widocznego kanbana
        current_kanban = self._tabs.currentWidget()
        color = current_kanban._color if isinstance(current_kanban, _ProjectKanban) else "#7C3AED"

        dlg = _EditTaskDialog(task, color, self)
        if dlg.exec() != QDialog.Accepted or not dlg.has_changes():
            return

        page_id = task["notion_page_id"]
        new_title = dlg.title()
        new_deadline = dlg.deadline()
        new_details = dlg.details()

        # zapis lokalny
        self._repo.update_task_fields_local(
            page_id,
            title=new_title if new_title != task.get("title") else None,
            deadline=new_deadline,
            details=new_details,
        )
        self._refresh_kanban_for_task(page_id)

        # sync do Notion w tle
        if self._fetcher and self._fetcher.is_configured():
            thread = _UpdateThread(
                self._fetcher, page_id,
                title=new_title if new_title != task.get("title") else None,
                deadline=new_deadline,
                details=new_details,
                parent=self,
            )
            thread.done.connect(lambda pid: self._on_update_synced(pid))
            thread.error.connect(lambda msg: logger.error("update task error: %s", msg))
            thread.start()
            self._action_threads.append(thread)

    def _on_update_synced(self, page_id: str) -> None:
        self._repo.mark_task_clean(page_id)
        self._refresh_kanban_for_task(page_id)

    # ── tworzenie zadania ────────────────────────────────────────────────────

    def _on_create_task(self, project_page_id: str, title: str,
                        deadline: str, details: str) -> None:
        if not self._fetcher or not self._fetcher.is_configured():
            return
        kanban = self._kanbans.get(project_page_id)
        if kanban:
            kanban.set_status("tworzę zadanie...", ok=True)

        thread = _CreateThread(
            self._fetcher, title, project_page_id,
            deadline or None, details or None, self,
        )
        thread.done.connect(lambda t: self._on_task_created(t, project_page_id))
        thread.error.connect(lambda msg: logger.error("create task error: %s", msg))
        thread.start()
        self._action_threads.append(thread)

    def _on_task_created(self, task, project_page_id: str) -> None:
        if task is None:
            return
        self._repo.insert_task_local(
            notion_page_id=task.page_id,
            title=task.title,
            status=task.status,
            deadline=task.deadline,
            details=task.details,
            project_page_id=project_page_id,
        )
        self._load_tasks_from_db(project_page_id)
        kanban = self._kanbans.get(project_page_id)
        if kanban:
            kanban.set_status("zadanie utworzone ✓", ok=True)

    # ── helper ────────────────────────────────────────────────────────────────

    def _refresh_kanban_for_task(self, page_id: str) -> None:
        for proj_pid, kanban in self._kanbans.items():
            tasks = self._repo.list_tasks_for_project(proj_pid)
            if any(t["notion_page_id"] == page_id for t in tasks):
                kanban.set_tasks(tasks)
                return

    # ── publiczne API ─────────────────────────────────────────────────────────

    def refresh_projects(self) -> None:
        self._load_pinned()
        if self._kanbans:
            self.sync_all()
