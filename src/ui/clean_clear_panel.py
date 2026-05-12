"""CleanClearPanel — skaner i czyszczenie plików MD projektu."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ── Style (spójne z cc_launcher_panel) ────────────────────────────────────────
_LBL_HEAD = "color:#9cdcfe;font-size:11px;font-weight:bold;"
_LBL_DIM  = "color:#5c6370;font-size:10px;"
_LBL_OK   = "color:#98c379;font-size:10px;"
_LBL_WARN = "color:#e5c07b;font-size:10px;"
_LBL_ERR  = "color:#e06c75;font-size:10px;"
_BTN = (
    "QPushButton{background:#2d2d2d;color:#cccccc;border:1px solid #454545;"
    "border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#3c3c3c}"
    "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
)
_BTN_ACCENT = (
    "QPushButton{background:#007acc;color:white;border:none;border-radius:3px;"
    "padding:5px 16px;font-weight:bold}"
    "QPushButton:hover{background:#1a8dd9}"
    "QPushButton:disabled{background:#1a3a4a;color:#5c8a9a}"
)
_BTN_DANGER = (
    "QPushButton{background:#5a1e1e;color:#e06c75;border:1px solid #7a3030;"
    "border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#7a3030}"
)
_CARD = "QFrame{background:#1e1e1e;border:1px solid #3c3c3c;border-radius:4px;padding:2px}"
_FONT_MONO  = QFont("Consolas", 9)
_FONT_SMALL = QFont("Segoe UI", 9)

# ── Stałe ────────────────────────────────────────────────────────────────────
STANDARD_FILES = ["CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md", "PLAN.md",
                  "CHANGELOG.md", "README.md"]

CAT_IMPORTANT = "ważne"
CAT_DEPENDS   = "zależy"
CAT_JUNK      = "nieważne"

# Heurystyka słów kluczowych
_KW_IMPORTANT = re.compile(
    r"\b(MUST|must|NEVER|never|ALWAYS|always|CRITICAL|critical|IMPORTANT|important"
    r"|zasada|ZASADA|wymóg|wymaganie|zakazane|obowiązkow|konwencja|zawsze|nigdy"
    r"|STACK|stack|python|pytest|pathlib|pysid|qt6|main\.py|src/)\b",
    re.IGNORECASE,
)
_KW_JUNK = re.compile(
    r"^(\s*#\s*[-=*]{3,}\s*$"           # separator
    r"|\s*$"                             # pusta linia
    r"|\s*<!--.*?-->\s*$"               # komentarz HTML
    r"|\s*\|\s*[-:]+\s*\|"             # separator tabeli
    r")",
)


# ── Model danych ──────────────────────────────────────────────────────────────
class LineInfo(NamedTuple):
    file: str          # nazwa pliku
    lineno: int        # numer linii (1-based)
    text: str          # treść linii
    category: str      # CAT_*


def classify_line(text: str) -> str:
    """Heurystyczna klasyfikacja linii."""
    if _KW_JUNK.match(text):
        return CAT_JUNK
    if _KW_IMPORTANT.search(text):
        return CAT_IMPORTANT
    stripped = text.strip()
    if not stripped:
        return CAT_JUNK
    if stripped.startswith("#"):
        return CAT_IMPORTANT   # nagłówki zawsze ważne
    if len(stripped) < 6:
        return CAT_JUNK
    return CAT_DEPENDS


def scan_project(project_path: Path) -> tuple[list[str], list[str]]:
    """Zwraca (standard_found, extra_found) — listy nazw plików."""
    standard, extra = [], []
    for name in STANDARD_FILES:
        if (project_path / name).exists():
            standard.append(name)
    all_md = {p.name for p in project_path.glob("*.md")}
    for name in sorted(all_md - set(STANDARD_FILES)):
        extra.append(name)
    return standard, extra


def parse_files(project_path: Path, filenames: list[str]) -> list[LineInfo]:
    """Parsuje pliki i klasyfikuje linie."""
    result: list[LineInfo] = []
    for fname in filenames:
        fp = project_path / fname
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            result.append(LineInfo(fname, i, line, classify_line(line)))
    return result


def stats_per_file(lines: list[LineInfo]) -> dict[str, dict[str, int]]:
    """Zwraca {filename: {cat: count}}."""
    out: dict[str, dict[str, int]] = {}
    for li in lines:
        s = out.setdefault(li.file, {CAT_IMPORTANT: 0, CAT_DEPENDS: 0, CAT_JUNK: 0})
        s[li.category] += 1
    return out


def build_cleaned(project_path: Path, lines: list[LineInfo],
                  remove_cats: set[str]) -> dict[str, str]:
    """Zwraca {filename: new_content} po usunięciu linii z remove_cats."""
    per_file: dict[str, list[LineInfo]] = {}
    for li in lines:
        per_file.setdefault(li.file, []).append(li)

    result = {}
    for fname, file_lines in per_file.items():
        kept = [li.text for li in file_lines if li.category not in remove_cats]
        result[fname] = "\n".join(kept)
    return result


def build_cleaning_md(lines: list[LineInfo], remove_cats: set[str]) -> str:
    """Generuje CLEANING.md z usuniętymi liniami."""
    per_file: dict[str, list[LineInfo]] = {}
    for li in lines:
        if li.category in remove_cats:
            per_file.setdefault(li.file, []).append(li)

    if not per_file:
        return "# CLEANING.md\n\n(brak usuniętych linii)\n"

    parts = ["# CLEANING.md\n"]
    for fname, file_lines in per_file.items():
        parts.append(f"\n## {fname}\n")
        for li in sorted(file_lines, key=lambda x: x.lineno):
            parts.append(f"{li.lineno:4d}: {li.text}")
    return "\n".join(parts) + "\n"


# ── Wątek klasyfikacji (placeholder — heurystyka synchroniczna) ───────────────
class ClassifyWorker(QThread):
    done = Signal(list)  # list[LineInfo]

    def __init__(self, project_path: Path, filenames: list[str]) -> None:
        super().__init__()
        self._project_path = project_path
        self._filenames = filenames

    def run(self) -> None:
        result = parse_files(self._project_path, self._filenames)
        self.done.emit(result)


# ── Dialog diff ───────────────────────────────────────────────────────────────
class _DiffDialog(QDialog):
    def __init__(self, diffs: dict[str, tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Podgląd zmian — przed i po czyszczeniu")
        self.resize(900, 600)

        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        info = QLabel("Poniżej prezentowane są zmiany. Kliknij OK aby zapisać, Anuluj aby porzucić.")
        info.setStyleSheet(_LBL_WARN)
        lay.addWidget(info)

        for fname, (before, after) in diffs.items():
            lbl = QLabel(fname, styleSheet=_LBL_HEAD)
            lay.addWidget(lbl)
            view = QTextEdit()
            view.setReadOnly(True)
            view.setFont(_FONT_MONO)
            view.setStyleSheet(
                "QTextEdit{background:#0d1117;border:1px solid #3c3c3c;"
                "border-radius:3px;padding:4px}"
            )
            self._render_diff(view, before, after)
            lay.addWidget(view, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    @staticmethod
    def _render_diff(view: QTextEdit, before: str, after: str) -> None:
        before_lines = set(before.splitlines())
        after_lines  = set(after.splitlines())

        fmt_keep = QTextCharFormat()
        fmt_keep.setForeground(QColor("#cccccc"))
        fmt_del = QTextCharFormat()
        fmt_del.setForeground(QColor("#e06c75"))
        fmt_del.setBackground(QColor("#2d1a1a"))

        cursor = view.textCursor()
        for line in before.splitlines():
            if line in after_lines:
                cursor.insertText(f"  {line}\n", fmt_keep)
            else:
                cursor.insertText(f"- {line}\n", fmt_del)


# ── Główny panel ──────────────────────────────────────────────────────────────
class CleanClearPanel(QWidget):
    """Panel czyszczenia plików MD projektu."""

    _DEFAULT_COLOR = "#9d9d9d"

    def __init__(self, parent: QWidget | None = None, slot_color: str = "") -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._lines: list[LineInfo] = []
        self._worker: ClassifyWorker | None = None
        self._slot_color: str = slot_color or self._DEFAULT_COLOR
        self._setup_ui()

    # ── Budowa UI ─────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(self._build_header())
        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([340, 700])
        root.addWidget(splitter, stretch=1)

        root.addWidget(self._build_action_bar())

    def _build_header(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("CleanClear — czyszczenie plików MD", styleSheet=_LBL_HEAD))
        row.addStretch()
        self._status_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._status_lbl.setFont(_FONT_SMALL)
        row.addWidget(self._status_lbl)
        return w

    def _build_toolbar(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._path_lbl = QLabel("(brak projektu)", styleSheet=_LBL_DIM)
        self._path_lbl.setFont(_FONT_MONO)
        row.addWidget(self._path_lbl, stretch=1)

        self._btn_scan = QPushButton("Skanuj projekt")
        self._btn_scan.setStyleSheet(_BTN_ACCENT)
        self._btn_scan.clicked.connect(self._on_scan)
        self._btn_scan.setEnabled(False)
        row.addWidget(self._btn_scan)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(120)
        self._progress.setTextVisible(False)
        self._progress.hide()
        row.addWidget(self._progress)

        return w

    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(6)

        # Pliki standardowe
        lbl1 = QLabel("Pliki standardowe", styleSheet=_LBL_HEAD)
        lay.addWidget(lbl1)
        self._std_list = QListWidget()
        self._std_list.setStyleSheet(
            "QListWidget{background:#111;border:1px solid #3c3c3c;border-radius:3px;}"
            "QListWidget::item{padding:2px 4px;color:#cccccc;}"
            "QListWidget::item:checked{color:#9cdcfe;}"
        )
        self._std_list.setMaximumHeight(130)
        self._std_list.itemClicked.connect(self._on_file_clicked)
        lay.addWidget(self._std_list)

        # Pliki dodatkowe
        lbl2 = QLabel("Pliki dodatkowe (.md)", styleSheet=_LBL_HEAD)
        lay.addWidget(lbl2)
        self._extra_list = QListWidget()
        self._extra_list.setStyleSheet(self._std_list.styleSheet())
        self._extra_list.setMaximumHeight(100)
        self._extra_list.itemClicked.connect(self._on_file_clicked)
        lay.addWidget(self._extra_list)

        # Statystyki per plik
        lbl3 = QLabel("Statystyki klasyfikacji", styleSheet=_LBL_HEAD)
        lay.addWidget(lbl3)

        self._stats_frame = QFrame()
        self._stats_frame.setStyleSheet(_CARD)
        self._stats_layout = QVBoxLayout(self._stats_frame)
        self._stats_layout.setContentsMargins(6, 4, 6, 4)
        self._stats_layout.setSpacing(2)
        self._stats_layout.addWidget(QLabel("(po skanowaniu)", styleSheet=_LBL_DIM))

        scroll = QScrollArea()
        scroll.setWidget(self._stats_frame)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        lay.addWidget(scroll, stretch=1)

        return w

    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(6)

        # Filtr kategorii
        filter_frame = QFrame()
        filter_frame.setStyleSheet(_CARD)
        flay = QHBoxLayout(filter_frame)
        flay.setContentsMargins(8, 6, 8, 6)
        flay.setSpacing(16)
        flay.addWidget(QLabel("Usuń kategorie:", styleSheet=_LBL_HEAD))
        self._chk_junk      = QCheckBox("nieważne")
        self._chk_depends   = QCheckBox("zależy")
        self._chk_important = QCheckBox("ważne")
        self._chk_junk.setChecked(True)
        for chk in (self._chk_junk, self._chk_depends, self._chk_important):
            chk.setStyleSheet("color:#cccccc;font-size:10px;")
            flay.addWidget(chk)
        flay.addStretch()
        lay.addWidget(filter_frame)

        # Zakładki: Klasyfikacja | Przeglądarka
        self._right_tabs = QTabWidget()
        self._right_tabs.setDocumentMode(True)
        c = self._slot_color
        self._right_tabs.setStyleSheet(
            f"QTabBar::tab{{background:#1a1a1a;color:#5c6370;"
            f"font-size:10px;padding:4px 14px;border:none;margin-right:2px;}}"
            f"QTabBar::tab:selected{{background:#1e1e1e;color:{c};"
            f"border-bottom:2px solid {c};}}"
            "QTabBar::tab:hover:!selected{background:#222222;color:#9d9d9d;}"
        )

        # ── Zakładka 0: Klasyfikacja ──
        self._lines_view = QTextEdit()
        self._lines_view.setReadOnly(True)
        self._lines_view.setFont(_FONT_MONO)
        self._lines_view.setStyleSheet(
            "QTextEdit{background:#0d1117;border:1px solid #3c3c3c;"
            "border-radius:3px;padding:6px}"
        )
        self._lines_view.setPlaceholderText("(uruchom Skanuj projekt aby załadować linie)")
        self._right_tabs.addTab(self._lines_view, "Klasyfikacja")

        # ── Zakładka 1: Przeglądarka pliku ──
        viewer_w = QWidget()
        vlay = QVBoxLayout(viewer_w)
        vlay.setContentsMargins(0, 4, 0, 0)
        vlay.setSpacing(4)

        viewer_hdr = QHBoxLayout()
        self._viewer_file_lbl = QLabel("(kliknij plik na liście)", styleSheet=_LBL_DIM)
        self._viewer_file_lbl.setFont(_FONT_MONO)
        viewer_hdr.addWidget(self._viewer_file_lbl, stretch=1)
        self._btn_viewer_reload = QPushButton("⟳")
        self._btn_viewer_reload.setFixedWidth(28)
        self._btn_viewer_reload.setStyleSheet(_BTN)
        self._btn_viewer_reload.clicked.connect(self._reload_viewer)
        viewer_hdr.addWidget(self._btn_viewer_reload)
        vlay.addLayout(viewer_hdr)

        self._file_viewer = QTextEdit()
        self._file_viewer.setReadOnly(True)
        self._file_viewer.setFont(_FONT_MONO)
        self._file_viewer.setStyleSheet(
            "QTextEdit{background:#0d1117;border:1px solid #3c3c3c;"
            "border-radius:3px;padding:6px;color:#cccccc;}"
        )
        self._file_viewer.setPlaceholderText("(kliknij plik na liście po lewej)")
        vlay.addWidget(self._file_viewer, stretch=1)
        self._right_tabs.addTab(viewer_w, "Przeglądarka")

        self._viewer_current_file: str | None = None
        lay.addWidget(self._right_tabs, stretch=1)

        return w

    def _build_action_bar(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(8)

        row.addStretch()

        self._btn_preview = QPushButton("Podgląd diff")
        self._btn_preview.setStyleSheet(_BTN)
        self._btn_preview.setEnabled(False)
        self._btn_preview.clicked.connect(self._on_preview)
        row.addWidget(self._btn_preview)

        self._btn_clean = QPushButton("Wyczyść i zapisz")
        self._btn_clean.setStyleSheet(_BTN_DANGER)
        self._btn_clean.setEnabled(False)
        self._btn_clean.clicked.connect(self._on_clean)
        row.addWidget(self._btn_clean)

        return w

    # ── Publiczny API ─────────────────────────────────────────────────────────

    def set_slot_color(self, color: str) -> None:
        """Aktualizuje kolor akcentu zakładek zgodnie z kolorem slotu."""
        self._slot_color = color or self._DEFAULT_COLOR
        c = self._slot_color
        self._right_tabs.setStyleSheet(
            f"QTabBar::tab{{background:#1a1a1a;color:#5c6370;"
            f"font-size:10px;padding:4px 14px;border:none;margin-right:2px;}}"
            f"QTabBar::tab:selected{{background:#1e1e1e;color:{c};"
            f"border-bottom:2px solid {c};}}"
            "QTabBar::tab:hover:!selected{background:#222222;color:#9d9d9d;}"
        )

    def load_project(self, project_path: str) -> None:
        """Ustawia projekt — wywołaj z zewnątrz przy zmianie slotu."""
        p = Path(project_path) if project_path else None
        self._project_path = p if (p and p.is_dir()) else None
        if self._project_path:
            self._path_lbl.setText(str(self._project_path))
            self._btn_scan.setEnabled(True)
            self._status_lbl.setText("")
        else:
            self._path_lbl.setText("(brak projektu)")
            self._btn_scan.setEnabled(False)
        self._reset_state()

    # ── Wewnętrzna logika ─────────────────────────────────────────────────────

    def _on_file_clicked(self, item: QListWidgetItem) -> None:
        """Kliknięcie pliku na liście — otwórz go w Przeglądarce."""
        fname = item.text()
        self._viewer_current_file = fname
        self._right_tabs.setCurrentIndex(1)
        self._load_viewer(fname)

    def _load_viewer(self, fname: str) -> None:
        if not self._project_path:
            return
        fp = self._project_path / fname
        self._viewer_file_lbl.setText(fname)
        if not fp.exists():
            self._file_viewer.setPlainText(f"(plik {fname} nie istnieje)")
            return
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            self._file_viewer.setPlainText(f"(błąd odczytu: {exc})")
            return

        # Kolorowanie składni Markdown: nagłówki, pogrubienie, linki, kod
        fmt_default = QTextCharFormat()
        fmt_default.setForeground(QColor("#cccccc"))
        fmt_h1 = QTextCharFormat()
        fmt_h1.setForeground(QColor("#9cdcfe"))
        fmt_h1.setFontWeight(700)
        fmt_h2 = QTextCharFormat()
        fmt_h2.setForeground(QColor("#7dd3fc"))
        fmt_h2.setFontWeight(700)
        fmt_h3 = QTextCharFormat()
        fmt_h3.setForeground(QColor("#60a5fa"))
        fmt_code = QTextCharFormat()
        fmt_code.setForeground(QColor("#f9c74f"))
        fmt_comment = QTextCharFormat()
        fmt_comment.setForeground(QColor("#5c6370"))
        fmt_bullet = QTextCharFormat()
        fmt_bullet.setForeground(QColor("#98c379"))

        self._file_viewer.clear()
        cursor = self._file_viewer.textCursor()
        for line in content.splitlines():
            if line.startswith("# "):
                cursor.insertText(line + "\n", fmt_h1)
            elif line.startswith("## "):
                cursor.insertText(line + "\n", fmt_h2)
            elif line.startswith("### ") or line.startswith("#### "):
                cursor.insertText(line + "\n", fmt_h3)
            elif line.startswith("```") or line.startswith("    "):
                cursor.insertText(line + "\n", fmt_code)
            elif line.startswith("<!--"):
                cursor.insertText(line + "\n", fmt_comment)
            elif re.match(r"^\s*[-*+] ", line) or re.match(r"^\s*\d+\. ", line):
                cursor.insertText(line + "\n", fmt_bullet)
            else:
                cursor.insertText(line + "\n", fmt_default)

        self._file_viewer.moveCursor(QTextCursor.MoveOperation.Start)

    def _reload_viewer(self) -> None:
        if self._viewer_current_file:
            self._load_viewer(self._viewer_current_file)

    def _reset_state(self) -> None:
        self._lines = []
        self._std_list.clear()
        self._extra_list.clear()
        self._lines_view.clear()
        self._file_viewer.clear()
        self._viewer_file_lbl.setText("(kliknij plik na liście)")
        self._viewer_current_file = None
        self._btn_preview.setEnabled(False)
        self._btn_clean.setEnabled(False)
        self._clear_stats()

    def _clear_stats(self) -> None:
        while self._stats_layout.count():
            item = self._stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _selected_filenames(self) -> list[str]:
        result = []
        for i in range(self._std_list.count()):
            item = self._std_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        for i in range(self._extra_list.count()):
            item = self._extra_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        return result

    def _remove_categories(self) -> set[str]:
        cats = set()
        if self._chk_junk.isChecked():
            cats.add(CAT_JUNK)
        if self._chk_depends.isChecked():
            cats.add(CAT_DEPENDS)
        if self._chk_important.isChecked():
            cats.add(CAT_IMPORTANT)
        return cats

    # ── Skanowanie ────────────────────────────────────────────────────────────

    def _on_scan(self) -> None:
        if not self._project_path:
            return
        self._reset_state()
        standard, extra = scan_project(self._project_path)

        for name in standard:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._std_list.addItem(item)

        for name in extra:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._extra_list.addItem(item)

        filenames = [name for name in standard]  # domyślnie skanuj standardowe
        if not filenames:
            self._status_lbl.setText("Brak plików MD w projekcie")
            self._status_lbl.setStyleSheet(_LBL_WARN)
            return

        self._progress.show()
        self._progress.setRange(0, 0)
        self._btn_scan.setEnabled(False)
        self._status_lbl.setText("Klasyfikuję linie…")
        self._status_lbl.setStyleSheet(_LBL_DIM)

        self._worker = ClassifyWorker(self._project_path, filenames)
        self._worker.done.connect(self._on_classify_done)
        self._worker.start()

    def _on_classify_done(self, lines: list[LineInfo]) -> None:
        self._lines = lines
        self._worker = None
        self._progress.hide()
        self._btn_scan.setEnabled(True)

        self._render_stats()
        self._render_lines()

        self._btn_preview.setEnabled(bool(lines))
        self._btn_clean.setEnabled(bool(lines))

        total = len(lines)
        junk = sum(1 for l in lines if l.category == CAT_JUNK)
        self._status_lbl.setText(f"{total} linii · {junk} do usunięcia (nieważne)")
        self._status_lbl.setStyleSheet(_LBL_OK)

    def _render_stats(self) -> None:
        self._clear_stats()
        stats = stats_per_file(self._lines)
        # nagłówek
        hdr = QWidget()
        hrow = QHBoxLayout(hdr)
        hrow.setContentsMargins(0, 0, 0, 0)
        for txt, style in [
            ("Plik", _LBL_HEAD),
            ("ważne", "color:#98c379;font-size:10px;"),
            ("zależy", "color:#e5c07b;font-size:10px;"),
            ("nieważne", "color:#e06c75;font-size:10px;"),
        ]:
            lbl = QLabel(txt, styleSheet=style)
            lbl.setFont(_FONT_SMALL)
            lbl.setMinimumWidth(60)
            hrow.addWidget(lbl)
        self._stats_layout.addWidget(hdr)

        for fname, counts in stats.items():
            row_w = QWidget()
            rlay = QHBoxLayout(row_w)
            rlay.setContentsMargins(0, 0, 0, 0)
            rlay.setSpacing(4)
            fn_lbl = QLabel(fname, styleSheet="color:#cccccc;font-size:9px;")
            fn_lbl.setFont(_FONT_MONO)
            fn_lbl.setMinimumWidth(60)
            rlay.addWidget(fn_lbl)
            for cat, style in [
                (CAT_IMPORTANT, "color:#98c379;font-size:10px;"),
                (CAT_DEPENDS,   "color:#e5c07b;font-size:10px;"),
                (CAT_JUNK,      "color:#e06c75;font-size:10px;"),
            ]:
                lbl = QLabel(str(counts.get(cat, 0)), styleSheet=style)
                lbl.setFont(_FONT_SMALL)
                lbl.setMinimumWidth(60)
                rlay.addWidget(lbl)
            self._stats_layout.addWidget(row_w)

        self._stats_layout.addStretch()

    def _render_lines(self) -> None:
        fmt_imp = QTextCharFormat()
        fmt_imp.setForeground(QColor("#98c379"))
        fmt_dep = QTextCharFormat()
        fmt_dep.setForeground(QColor("#e5c07b"))
        fmt_jnk = QTextCharFormat()
        fmt_jnk.setForeground(QColor("#5c6370"))
        fmt_hdr = QTextCharFormat()
        fmt_hdr.setForeground(QColor("#9cdcfe"))
        fmt_hdr.setFontWeight(700)

        self._lines_view.clear()
        cursor = self._lines_view.textCursor()

        current_file = None
        for li in self._lines:
            if li.file != current_file:
                current_file = li.file
                cursor.insertText(f"\n── {li.file} ──\n", fmt_hdr)

            fmt = {CAT_IMPORTANT: fmt_imp, CAT_DEPENDS: fmt_dep, CAT_JUNK: fmt_jnk}.get(
                li.category, fmt_dep
            )
            prefix = {"ważne": "✓", "zależy": "?", "nieważne": "✗"}.get(li.category, " ")
            cursor.insertText(f"{li.lineno:4d} {prefix} {li.text}\n", fmt)

        self._lines_view.moveCursor(QTextCursor.MoveOperation.Start)

    # ── Podgląd diff ──────────────────────────────────────────────────────────

    def _on_preview(self) -> None:
        if not self._project_path or not self._lines:
            return
        remove_cats = self._remove_categories()
        if not remove_cats:
            QMessageBox.information(self, "Nic do usunięcia",
                                    "Zaznacz co najmniej jedną kategorię do usunięcia.")
            return

        selected = self._selected_filenames()
        lines = [l for l in self._lines if l.file in selected] if selected else self._lines

        cleaned = build_cleaned(self._project_path, lines, remove_cats)
        diffs: dict[str, tuple[str, str]] = {}
        for fname, new_content in cleaned.items():
            orig = (self._project_path / fname).read_text(encoding="utf-8", errors="replace")
            if orig != new_content:
                diffs[fname] = (orig, new_content)

        if not diffs:
            QMessageBox.information(self, "Brak zmian",
                                    "Żadne linie nie zostaną usunięte przy wybranych ustawieniach.")
            return

        dlg = _DiffDialog(diffs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._do_clean(lines, remove_cats, cleaned)

    # ── Czyszczenie ───────────────────────────────────────────────────────────

    def _on_clean(self) -> None:
        if not self._project_path or not self._lines:
            return
        remove_cats = self._remove_categories()
        if not remove_cats:
            QMessageBox.information(self, "Nic do usunięcia",
                                    "Zaznacz co najmniej jedną kategorię do usunięcia.")
            return

        selected = self._selected_filenames()
        lines = [l for l in self._lines if l.file in selected] if selected else self._lines

        ans = QMessageBox.question(
            self, "Potwierdzenie",
            f"Usunąć linie kategorii {', '.join(remove_cats)} z {len(set(l.file for l in lines))} pliku/ów?\n"
            "Operacja jest nieodwracalna (bez podglądu).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        cleaned = build_cleaned(self._project_path, lines, remove_cats)
        self._do_clean(lines, remove_cats, cleaned)

    def _do_clean(self, lines: list[LineInfo], remove_cats: set[str],
                  cleaned: dict[str, str]) -> None:
        if not self._project_path:
            return
        errors = []
        saved = 0
        for fname, content in cleaned.items():
            try:
                (self._project_path / fname).write_text(content, encoding="utf-8")
                saved += 1
            except Exception as exc:
                errors.append(f"{fname}: {exc}")

        # Zapisz CLEANING.md
        cleaning_content = build_cleaning_md(lines, remove_cats)
        try:
            (self._project_path / "CLEANING.md").write_text(cleaning_content, encoding="utf-8")
        except Exception as exc:
            errors.append(f"CLEANING.md: {exc}")

        if errors:
            QMessageBox.warning(self, "Błędy zapisu", "\n".join(errors))
        else:
            self._status_lbl.setText(f"✓ Zapisano {saved} plik(ów) + CLEANING.md")
            self._status_lbl.setStyleSheet(_LBL_OK)

        # Odśwież widok
        self._on_scan()
