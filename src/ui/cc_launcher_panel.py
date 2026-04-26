"""Panel 'Sesje CC' — uruchamianie i monitorowanie sesji Claude Code."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.cc_launcher.launcher_config import (
    CC_EFFORTS,
    CC_MODELS,
    CC_PERMISSION_MODES,
    DEFAULT_VIBE_PROMPT,
    LauncherConfig,
    SlotConfig,
    load_launcher_config,
    save_launcher_config,
)
from src.cc_launcher.project_stats import ProjectStats, fmt_size, get_project_stats
from src.cc_launcher.session_history import (
    SessionHistorySummary,
    get_session_history,
)
from src.cc_launcher.session_manager import (
    open_vscode_window,
    prepare_and_launch,
    terminate_vscode_session,
)
from src.projektant.template_parser import (
    parse_dict,
    parse_list,
    read_section,
)
from src.utils.plan_parser import PlanData, get_section, read_plan, write_plan
from src.ui.zadania_panel import ZadaniaPanel as _ZadaniaPanel
from src.workflow import WorkflowRunner
from src.watchers.session_watcher import (
    SessionWatcher,
    TerminalSnapshot,
    read_transcript_tail,
)

SLOT_COLORS = ["#2dd4bf", "#fbbf24", "#a78bfa", "#fb7185"]
SLOT_NAMES = ["Projekt 1", "Projekt 2", "Projekt 3", "Projekt 4"]

_FONT_MONO = QFont("Consolas", 9)
_FONT_SMALL = QFont("Segoe UI", 9)

_BTN = (
    "QPushButton{background:#2d2d2d;color:#cccccc;border:1px solid #454545;"
    "border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#3c3c3c}"
    "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
)
_BTN_ACCENT = (
    "QPushButton{background:#007acc;color:white;border:none;"
    "border-radius:3px;padding:5px 16px;font-weight:bold}"
    "QPushButton:hover{background:#1a8dd9}"
    "QPushButton:disabled{background:#1a3a4a;color:#5c8a9a}"
)
_BTN_DANGER = (
    "QPushButton{background:#5a1e1e;color:#e06c75;"
    "border:1px solid #7a3030;border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#7a3030}"
)
_BTN_GREEN = (
    "QPushButton{background:#1a3a1a;color:#98c379;"
    "border:1px solid #2a5a2a;border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#2a5a2a}"
)
_LBL_HEAD = "color:#9cdcfe;font-size:11px;font-weight:bold;"
_LBL_KEY = "color:#9cdcfe;font-size:10px;"
_LBL_VAL = "color:#cccccc;font-size:10px;"
_LBL_DIM = "color:#5c6370;font-size:10px;"
_LBL_OK = "color:#98c379;font-size:10px;"
_LBL_WARN = "color:#e5c07b;font-size:10px;"
_LBL_ERR = "color:#e06c75;font-size:10px;"
_CARD = (
    "QFrame{background:#1e1e1e;border:1px solid #3c3c3c;"
    "border-radius:4px;padding:2px}"
)


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color:#3c3c3c;")
    return f


def _kv_row(key: str, value_widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    k = QLabel(key, styleSheet=_LBL_KEY)
    k.setFixedWidth(120)
    row.addWidget(k)
    row.addWidget(value_widget)
    row.addStretch()
    return row


def _val(text: str = "—", style: str = _LBL_VAL) -> QLabel:
    lbl = QLabel(text, styleSheet=style)
    lbl.setFont(_FONT_SMALL)
    return lbl


class _StatusBar(QLabel):
    """Pasek stanu slotu — faza i czas."""

    _ICONS = {"working": "⚙", "waiting": "⏸"}
    _COLORS = {"working": "#98c379", "waiting": "#e5c07b"}

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFont(_FONT_MONO)
        self.setFixedHeight(22)
        self._idle()

    def refresh(self, snap: TerminalSnapshot) -> None:
        if snap.is_file_missing:
            self._idle()
            return
        icon = self._ICONS.get(snap.phase or "", "●")
        clr = self._COLORS.get(snap.phase or "", "#5c6370")
        s = snap.seconds_since_change
        mins = s // 60
        secs = s % 60
        elapsed = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
        self.setText(f"  {icon}  {snap.phase or '—'}  ·  {elapsed} temu  ")
        self.setStyleSheet(
            f"background:#252526;color:{clr};"
            f"border-left:3px solid {self._color};padding:2px 4px;"
        )

    def _idle(self) -> None:
        self.setText("  —  brak aktywnej sesji  ")
        self.setStyleSheet(
            f"background:#252526;color:#5c6370;"
            f"border-left:3px solid {self._color};padding:2px 4px;"
        )


class GitInitDialog(QDialog):
    """Dialog inicjalizacji repozytorium git dla projektu bez .git."""

    def __init__(self, project_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Inicjalizacja repozytorium Git")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._project_path = project_path
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Nagłówek z ostrzeżeniem
        warn = QLabel("Katalog projektu nie posiada repozytorium git.")
        warn.setStyleSheet("color:#e5c07b;font-size:12px;font-weight:bold;")
        root.addWidget(warn)

        path_lbl = QLabel(self._project_path)
        path_lbl.setStyleSheet("color:#5c6370;font-size:10px;font-family:Consolas;")
        path_lbl.setWordWrap(True)
        root.addWidget(path_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#3c3c3c;")
        root.addWidget(sep)

        # Formularz
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        _le = ("QLineEdit{background:#1e1e1e;color:#cccccc;border:1px solid #454545;"
               "border-radius:3px;padding:4px 8px;font-family:Consolas;font-size:11px;}"
               "QLineEdit:focus{border-color:#007acc;}")

        self._remote_edit = QLineEdit()
        self._remote_edit.setPlaceholderText("https://github.com/uzytkownik/repo.git  (opcjonalnie)")
        self._remote_edit.setStyleSheet(_le)
        self._remote_edit.textChanged.connect(self._update_summary)
        form.addRow("Remote URL:", self._remote_edit)

        self._branch_combo = QComboBox()
        self._branch_combo.addItems(["master", "main", "develop"])
        self._branch_combo.setEditable(True)
        self._branch_combo.setStyleSheet(
            "QComboBox{background:#1e1e1e;color:#cccccc;border:1px solid #454545;"
            "border-radius:3px;padding:3px 6px;font-family:Consolas;font-size:11px;}"
            "QComboBox QAbstractItemView{background:#252526;color:#cccccc;"
            "selection-background-color:#094771;}"
        )
        self._branch_combo.currentTextChanged.connect(self._update_summary)
        form.addRow("Gałąź:", self._branch_combo)

        self._msg_edit = QLineEdit("feat: initial commit")
        self._msg_edit.setStyleSheet(_le)
        form.addRow("Commit message:", self._msg_edit)

        root.addLayout(form)

        # Podsumowanie kroków
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#3c3c3c;")
        root.addWidget(sep2)

        root.addWidget(QLabel("Zostaną wykonane:", styleSheet="color:#9cdcfe;font-size:11px;"))
        self._summary = QPlainTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setFixedHeight(100)
        self._summary.setFont(QFont("Consolas", 9))
        self._summary.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#98c379;"
            "border:1px solid #3c3c3c;border-radius:3px;padding:4px;}"
        )
        root.addWidget(self._summary)

        # Przyciski
        btns = QDialogButtonBox()
        self._btn_ok = btns.addButton("Utwórz repozytorium", QDialogButtonBox.ButtonRole.AcceptRole)
        self._btn_ok.setStyleSheet(
            "QPushButton{background:#1a3a1a;color:#98c379;border:1px solid #2a5a2a;"
            "border-radius:3px;padding:5px 16px;font-weight:bold;}"
            "QPushButton:hover{background:#2a5a2a;}"
        )
        btn_cancel = btns.addButton("Anuluj", QDialogButtonBox.ButtonRole.RejectRole)
        btn_cancel.setStyleSheet(_BTN)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._update_summary()

    def _update_summary(self) -> None:
        p = self._project_path
        branch = self._branch_combo.currentText().strip() or "master"
        remote = self._remote_edit.text().strip()
        lines = [
            f"$ git init -b {branch}  ({p})",
            "$ git add -A",
            f"$ git commit -m \"{self._msg_edit.text().strip() or 'feat: initial commit'}\"",
        ]
        if remote:
            lines += [
                f"$ git remote add origin {remote}",
                f"$ git push -u origin {branch}",
            ]
        else:
            lines.append("(push pominięty — brak remote URL)")
        self._summary.setPlainText("\n".join(lines))

    @property
    def remote_url(self) -> str:
        return self._remote_edit.text().strip()

    @property
    def branch(self) -> str:
        return self._branch_combo.currentText().strip() or "master"

    @property
    def commit_message(self) -> str:
        return self._msg_edit.text().strip()


class ProjectSlotWidget(QWidget):
    """Widget jednego slotu — 5 zakładek: Dane, PLAN, Historia, Sesje, Vibe Code."""

    config_changed = Signal()
    launch_requested = Signal(int)
    window_requested = Signal(int)
    stop_requested = Signal(int)
    stop_completed = Signal(int)

    def __init__(self, slot_id: int, config: SlotConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slot_id = slot_id
        self._config = config
        self._color = SLOT_COLORS[slot_id - 1]
        self._plan_data: PlanData | None = None
        self._stats: ProjectStats | None = None
        self._history: SessionHistorySummary | None = None

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._on_debounce)

        self._stop_pending = False
        self._workflow = WorkflowRunner(parent=self)
        self._workflow.operation_done.connect(self._on_workflow_done)

        self._setup_ui()
        self._connect_signals()
        self._load_config()

    # ------------------------------------------------------------------ #
    # Budowanie UI                                                          #
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        self._status_bar = _StatusBar(self._color)
        root.addWidget(self._status_bar)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        # Zakładki sekcji w kolorze slotu z czarnym tekstem
        c = self._color
        # Ciemniejsza wersja dla nieaktywnych zakładek (hex * 0.7 przez nakładkę alpha)
        self._tabs.setStyleSheet(f"""
            QTabBar::tab {{
                background: {c}88;
                color: #0a0a0a;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 14px;
                border: none;
                margin-right: 2px;
                border-radius: 3px 3px 0 0;
            }}
            QTabBar::tab:selected {{
                background: {c};
                color: #000000;
                border-bottom: 2px solid #000000;
            }}
            QTabBar::tab:hover:!selected {{
                background: {c}bb;
                color: #000000;
            }}
        """)
        root.addWidget(self._tabs, stretch=1)

        self._tabs.addTab(self._build_dane(), "Dane")
        self._tabs.addTab(self._build_plan(), "ZADANIA")
        self._tabs.addTab(self._build_zadaniowiec(), "ZADANIOWIEC")
        self._tabs.addTab(self._build_pcc(), "PLAN.md")
        self._tabs.addTab(self._build_md_file("CLAUDE.md"), "CLAUDE.md")
        self._tabs.addTab(self._build_md_file("ARCHITECTURE.md"), "ARCHITECTURE.md")
        self._tabs.addTab(self._build_md_file("CONVENTIONS.md"), "CONVENTIONS.md")
        self._tabs.addTab(self._build_historia_sesje_vibe(), "Sesje")

        root.addWidget(_sep())
        root.addWidget(self._build_action_bar())

    # ---- Dane ---------------------------------------------------------- #

    def _build_dane(self) -> QWidget:
        """Układ poziomy: ścieżka u góry + 2×2 grid kart poniżej (bez scrolla)."""
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Ścieżka projektu (cała szerokość) ──────────────────────────
        outer.addWidget(QLabel("Ścieżka projektu", styleSheet=_LBL_HEAD))
        path_row = QHBoxLayout()
        self._path_edit = QPlainTextEdit()
        self._path_edit.setFixedHeight(34)
        self._path_edit.setFont(_FONT_MONO)
        self._path_edit.setPlaceholderText("C:\\Projekty\\moj-projekt")
        path_row.addWidget(self._path_edit)
        self._btn_browse = QPushButton("…")
        self._btn_browse.setFixedWidth(30)
        self._btn_browse.setStyleSheet(_BTN)
        path_row.addWidget(self._btn_browse)
        outer.addLayout(path_row)

        # ── Grid 2×2: Konfiguracja | Stan sesji // Statystyki | Kluczowe pliki ──
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)

        # ── (0,0) Konfiguracja startowa ───────────────────────────────
        konfig = QFrame()
        konfig.setStyleSheet(_CARD)
        kl = QVBoxLayout(konfig)
        kl.setContentsMargins(8, 6, 8, 6)
        kl.setSpacing(4)
        kl.addWidget(QLabel("Konfiguracja startowa", styleSheet=_LBL_HEAD))

        self._model_combo = QComboBox()
        self._model_combo.addItems(CC_MODELS)
        self._model_combo.setFont(_FONT_MONO)
        kl.addLayout(_kv_row("Model:", self._model_combo))

        self._effort_combo = QComboBox()
        self._effort_combo.addItems(CC_EFFORTS)
        self._effort_combo.setFont(_FONT_MONO)
        kl.addLayout(_kv_row("Effort:", self._effort_combo))

        self._perm_combo = QComboBox()
        self._perm_combo.addItems(list(CC_PERMISSION_MODES.keys()))
        self._perm_combo.setFont(_FONT_MONO)
        kl.addLayout(_kv_row("Uprawnienia:", self._perm_combo))
        kl.addStretch()
        grid.addWidget(konfig, 0, 0)

        # ── (0,1) Stan aktywnej sesji ─────────────────────────────────
        stan = QFrame()
        stan.setStyleSheet(_CARD)
        sl = QVBoxLayout(stan)
        sl.setContentsMargins(8, 6, 8, 6)
        sl.setSpacing(2)
        sl.addWidget(QLabel("Stan aktywnej sesji", styleSheet=_LBL_HEAD))
        self._lbl_phase = _val()
        self._lbl_model_live = _val()
        self._lbl_cost = _val()
        self._lbl_ctx = _val()
        sl.addLayout(_kv_row("Faza:", self._lbl_phase))
        sl.addLayout(_kv_row("Model:", self._lbl_model_live))
        sl.addLayout(_kv_row("Koszt:", self._lbl_cost))
        sl.addLayout(_kv_row("Ctx%:", self._lbl_ctx))
        sl.addStretch()
        grid.addWidget(stan, 0, 1)

        # ── (1,0) Statystyki projektu ─────────────────────────────────
        stats = QFrame()
        stats.setStyleSheet(_CARD)
        stl = QVBoxLayout(stats)
        stl.setContentsMargins(8, 6, 8, 6)
        stl.setSpacing(2)
        stats_hdr = QHBoxLayout()
        stats_hdr.addWidget(QLabel("Statystyki projektu", styleSheet=_LBL_HEAD))
        stats_hdr.addStretch()
        self._btn_stats_refresh = QPushButton("⟳")
        self._btn_stats_refresh.setFixedWidth(28)
        self._btn_stats_refresh.setStyleSheet(_BTN)
        stats_hdr.addWidget(self._btn_stats_refresh)
        stl.addLayout(stats_hdr)

        self._lbl_files = _val()
        self._lbl_size = _val()
        self._lbl_git = _val()
        self._lbl_git_url = _val()
        self._lbl_branch = _val()
        stl.addLayout(_kv_row("Pliki/foldery:", self._lbl_files))
        stl.addLayout(_kv_row("Rozmiar:", self._lbl_size))
        stl.addLayout(_kv_row("Git:", self._lbl_git))
        stl.addLayout(_kv_row("Remote:", self._lbl_git_url))
        stl.addLayout(_kv_row("Gałąź:", self._lbl_branch))
        stl.addStretch()
        grid.addWidget(stats, 1, 0)

        # ── (1,1) Kluczowe pliki projektu ─────────────────────────────
        kfiles = QFrame()
        kfiles.setStyleSheet(_CARD)
        kfl = QVBoxLayout(kfiles)
        kfl.setContentsMargins(8, 6, 8, 6)
        kfl.setSpacing(2)
        kfl.addWidget(QLabel("Kluczowe pliki projektu", styleSheet=_LBL_HEAD))
        self._key_file_labels: dict[str, QLabel] = {}
        from src.cc_launcher.project_stats import KEY_FILES
        for fname in KEY_FILES:
            lbl = _val("—", _LBL_DIM)
            self._key_file_labels[fname] = lbl
            kfl.addLayout(_kv_row(fname + ":", lbl))
        kfl.addStretch()
        grid.addWidget(kfiles, 1, 1)

        outer.addLayout(grid, stretch=1)
        return w

    # ---- PLAN ---------------------------------------------------------- #

    def _build_plan(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        top = QHBoxLayout()
        self._lbl_plan_path = QLabel("", styleSheet=_LBL_DIM)
        self._lbl_plan_path.setFont(_FONT_MONO)
        top.addWidget(self._lbl_plan_path, stretch=1)
        self._btn_plan_refresh = QPushButton("Odśwież")
        self._btn_plan_refresh.setStyleSheet(_BTN)
        self._btn_plan_save = QPushButton("Zapisz")
        self._btn_plan_save.setStyleSheet(_BTN)
        self._btn_plan_save.setEnabled(False)
        top.addWidget(self._btn_plan_refresh)
        top.addWidget(self._btn_plan_save)
        lay.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._plan_editor = QPlainTextEdit()
        self._plan_editor.setFont(_FONT_MONO)
        self._plan_editor.setPlaceholderText(
            "Brak pliku PLAN.md lub nie ustawiono ścieżki projektu."
        )
        splitter.addWidget(self._plan_editor)

        summary = QFrame()
        summary.setStyleSheet(_CARD)
        s_lay = QVBoxLayout(summary)
        s_lay.setContentsMargins(8, 6, 8, 6)
        s_lay.setSpacing(3)
        s_lay.addWidget(QLabel("Podsumowanie:", styleSheet=_LBL_KEY))
        self._lbl_plan_stan = QLabel("Stan: —", styleSheet=_LBL_VAL, wordWrap=True)
        self._lbl_plan_active = QLabel("Aktywne: —", styleSheet=_LBL_VAL, wordWrap=True)
        s_lay.addWidget(self._lbl_plan_stan)
        s_lay.addWidget(self._lbl_plan_active)
        splitter.addWidget(summary)
        splitter.setSizes([350, 80])

        lay.addWidget(splitter, stretch=1)
        return w

    # ---- ZADANIOWIEC --------------------------------------------------- #

    def _build_zadaniowiec(self) -> QWidget:
        """Osadzony ZadaniaPanel — ładuje projekt slotu automatycznie."""
        self._zadaniowiec = _ZadaniaPanel()
        return self._zadaniowiec

    # ---- CLAUDE.md / ARCHITECTURE.md / CONVENTIONS.md ----------------- #

    _RE_HEADING = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    _RE_SECTION_TAG = re.compile(
        r"<!--\s*SECTION:(\w+)\s*-->(.*?)<!--\s*/SECTION:\1\s*-->", re.DOTALL
    )

    def _parse_md_sections(self, text: str) -> list[tuple[str, str]]:
        """Parsuje treść MD na listę (nagłówek, treść).
        Priorytet: <!-- SECTION:x --> tagi, potem ## nagłówki.
        """
        tag_hits = self._RE_SECTION_TAG.findall(text)
        if tag_hits:
            return [(f"[{name}]", body.strip()) for name, body in tag_hits]
        matches = list(self._RE_HEADING.finditer(text))
        result = []
        for i, m in enumerate(matches):
            heading = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            result.append((heading, text[start:end].strip()))
        return result

    def _build_md_file(self, filename: str) -> QWidget:
        """Buduje zakładkę dla jednego pliku MD: sekcje + changelog zmian."""
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Pasek narzędzi
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        lbl_path = QLabel("", styleSheet=_LBL_DIM)
        lbl_path.setFont(_FONT_MONO)
        toolbar.addWidget(lbl_path, stretch=1)
        btn_refresh = QPushButton("⟳  Odśwież")
        btn_refresh.setStyleSheet(_BTN)
        btn_refresh.setFixedWidth(90)
        toolbar.addWidget(btn_refresh)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Górna część — sekcje pliku
        sections_scroll = QScrollArea()
        sections_scroll.setWidgetResizable(True)
        sections_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sections_container = QWidget()
        sections_layout = QVBoxLayout(sections_container)
        sections_layout.setContentsMargins(8, 6, 8, 6)
        sections_layout.setSpacing(6)
        sections_layout.addStretch()
        sections_scroll.setWidget(sections_container)
        splitter.addWidget(sections_scroll)

        # Dolna część — changelog zmian
        changelog_frame = QFrame()
        changelog_frame.setStyleSheet(_CARD)
        cl_lay = QVBoxLayout(changelog_frame)
        cl_lay.setContentsMargins(8, 4, 8, 4)
        cl_lay.setSpacing(2)
        cl_lay.addWidget(QLabel("Zmiany sekcji:", styleSheet=_LBL_KEY))
        changelog_view = QPlainTextEdit()
        changelog_view.setReadOnly(True)
        changelog_view.setFont(_FONT_MONO)
        changelog_view.setFixedHeight(110)
        changelog_view.setPlaceholderText("(brak zarejestrowanych zmian)")
        cl_lay.addWidget(changelog_view)
        splitter.addWidget(changelog_frame)

        splitter.setSizes([420, 130])
        root.addWidget(splitter, stretch=1)

        # Przechowaj referencje jako atrybuty slotu
        safe = filename.replace(".", "_")
        setattr(self, f"_md_path_lbl_{safe}", lbl_path)
        setattr(self, f"_md_sections_layout_{safe}", sections_layout)
        setattr(self, f"_md_changelog_view_{safe}", changelog_view)
        btn_refresh.clicked.connect(lambda: self._reload_md_file(filename))

        return w

    def _reload_md_file(self, filename: str) -> None:
        """Wczytuje plik MD, parsuje sekcje, wykrywa zmiany i odświeża widok."""
        safe = filename.replace(".", "_")
        path_lbl: QLabel = getattr(self, f"_md_path_lbl_{safe}", None)
        sections_layout: QVBoxLayout = getattr(self, f"_md_sections_layout_{safe}", None)
        changelog_view: QPlainTextEdit = getattr(self, f"_md_changelog_view_{safe}", None)

        project_path = self._path_edit.toPlainText().strip()
        if not project_path:
            if path_lbl:
                path_lbl.setText("(brak ścieżki projektu)")
            return

        file_path = Path(project_path) / filename
        if path_lbl:
            path_lbl.setText(str(file_path))

        if not file_path.exists():
            if sections_layout:
                self._clear_sections_layout(sections_layout)
                lbl = QLabel(f"Plik {filename} nie istnieje w katalogu projektu.",
                             styleSheet=_LBL_WARN)
                lbl.setWordWrap(True)
                sections_layout.insertWidget(sections_layout.count() - 1, lbl)
            return

        current_text = file_path.read_text(encoding="utf-8")

        # Wykryj i zapisz zmiany
        if changelog_view:
            changes = self._detect_md_changes(project_path, filename, current_text)
            if changes:
                existing = changelog_view.toPlainText()
                new_lines = "\n".join(
                    f"{c['ts']}  [{c['action'].upper():8}]  {c['section']}  →  {c['preview']}"
                    for c in changes
                )
                changelog_view.setPlainText(new_lines + ("\n\n" + existing if existing else ""))

            # Załaduj pełny changelog dla tego pliku
            self._load_md_changelog(project_path, filename, changelog_view)

        # Renderuj sekcje
        if sections_layout:
            self._clear_sections_layout(sections_layout)
            sections = self._parse_md_sections(current_text)
            if not sections:
                lbl = QLabel("(plik nie zawiera sekcji ## lub <!-- SECTION -->)",
                             styleSheet=_LBL_DIM)
                sections_layout.insertWidget(sections_layout.count() - 1, lbl)
                return
            for heading, body in sections:
                # Nagłówek sekcji
                h_lbl = QLabel(heading, styleSheet=_LBL_HEAD)
                h_lbl.setFont(QFont("Consolas", 10))
                sections_layout.insertWidget(sections_layout.count() - 1, h_lbl)
                # Treść sekcji
                txt = QPlainTextEdit()
                txt.setReadOnly(True)
                txt.setFont(_FONT_MONO)
                txt.setPlainText(body if body else "(pusta sekcja)")
                txt.setFixedHeight(max(60, min(220, body.count("\n") * 16 + 36)))
                txt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                sections_layout.insertWidget(sections_layout.count() - 1, txt)
                # Separator
                sections_layout.insertWidget(sections_layout.count() - 1, _sep())

    def _clear_sections_layout(self, layout: QVBoxLayout) -> None:
        """Usuwa wszystkie widgety z layoutu sekcji (poza ostatnim stretch)."""
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _detect_md_changes(
        self, project_path: str, filename: str, current_text: str
    ) -> list[dict]:
        """Porównuje bieżącą treść z snapshotem, zapisuje zmiany do changelog."""
        snap_dir = Path(project_path) / "logs" / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"{filename}.snap"

        old_text = snap_path.read_text(encoding="utf-8") if snap_path.exists() else ""
        if old_text == current_text:
            return []

        old_secs = dict(self._parse_md_sections(old_text)) if old_text else {}
        new_secs = dict(self._parse_md_sections(current_text))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entries = []
        for key in sorted(set(old_secs) | set(new_secs)):
            old_b, new_b = old_secs.get(key, ""), new_secs.get(key, "")
            if old_b == new_b:
                continue
            action = "dodano" if not old_b else ("usunięto" if not new_b else "zmieniono")
            preview = (new_b or old_b)[:80].replace("\n", " ")
            entries.append({"ts": ts, "file": filename, "section": key,
                            "action": action, "preview": preview})

        if entries:
            cl_path = Path(project_path) / "logs" / "changelog.jsonl"
            cl_path.parent.mkdir(parents=True, exist_ok=True)
            with cl_path.open("a", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            snap_path.write_text(current_text, encoding="utf-8")

        return entries

    def _load_md_changelog(
        self, project_path: str, filename: str, view: QPlainTextEdit
    ) -> None:
        """Wczytuje ostatnie wpisy changelog dla danego pliku i wyświetla w widoku."""
        cl_path = Path(project_path) / "logs" / "changelog.jsonl"
        if not cl_path.exists():
            view.setPlainText("(brak zarejestrowanych zmian)")
            return
        lines = cl_path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("file") != filename:
                continue
            entries.append(
                f"{e.get('ts','')}  [{e.get('action',''):8}]  "
                f"{e.get('section','')}  →  {e.get('preview','')[:70]}"
            )
            if len(entries) >= 40:
                break
        view.setPlainText("\n".join(entries) if entries else "(brak zmian dla tego pliku)")

    # ---- PCC ----------------------------------------------------------- #

    def _build_pcc(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        self._pcc_path_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._pcc_path_lbl.setFont(_FONT_MONO)
        toolbar.addWidget(self._pcc_path_lbl, stretch=1)
        btn_refresh = QPushButton("⟳  Odśwież")
        btn_refresh.setStyleSheet(_BTN)
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self.reload_pcc)
        toolbar.addWidget(btn_refresh)
        outer.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 6, 8, 12)
        lay.setSpacing(8)

        # Meta
        lay.addWidget(QLabel("Stan rundy", styleSheet=_LBL_HEAD))
        meta_card = QFrame()
        meta_card.setStyleSheet(_CARD)
        meta_lay = QVBoxLayout(meta_card)
        meta_lay.setContentsMargins(8, 6, 8, 6)
        meta_lay.setSpacing(3)
        self._pcc_status = QLabel("—", styleSheet=_LBL_VAL)
        self._pcc_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._pcc_goal = QLabel("—", styleSheet=_LBL_VAL, wordWrap=True)
        self._pcc_session = QLabel("—", styleSheet=_LBL_VAL)
        self._pcc_updated = QLabel("—", styleSheet=_LBL_DIM)
        meta_lay.addLayout(_kv_row("Status:", self._pcc_status))
        meta_lay.addLayout(_kv_row("Cel:", self._pcc_goal))
        meta_lay.addLayout(_kv_row("Sesja:", self._pcc_session))
        meta_lay.addLayout(_kv_row("Zaktualizowany:", self._pcc_updated))
        lay.addWidget(meta_card)

        # Current
        lay.addWidget(QLabel("Aktywne zadanie", styleSheet=_LBL_HEAD))
        cur_card = QFrame()
        cur_card.setStyleSheet(_CARD)
        cur_lay = QVBoxLayout(cur_card)
        cur_lay.setContentsMargins(8, 6, 8, 6)
        cur_lay.setSpacing(3)
        self._pcc_cur_task = QLabel("—", styleSheet=_LBL_VAL, wordWrap=True)
        self._pcc_cur_task.setFont(QFont("Consolas", 10))
        self._pcc_cur_file = QLabel("—", styleSheet=_LBL_DIM)
        self._pcc_cur_started = QLabel("—", styleSheet=_LBL_DIM)
        cur_lay.addLayout(_kv_row("Zadanie:", self._pcc_cur_task))
        cur_lay.addLayout(_kv_row("Plik:", self._pcc_cur_file))
        cur_lay.addLayout(_kv_row("Rozpoczete:", self._pcc_cur_started))
        lay.addWidget(cur_card)

        # Next
        lay.addWidget(QLabel("Następne", styleSheet=_LBL_HEAD))
        self._pcc_next = QPlainTextEdit()
        self._pcc_next.setReadOnly(True)
        self._pcc_next.setFont(_FONT_MONO)
        self._pcc_next.setFixedHeight(100)
        self._pcc_next.setPlaceholderText("(brak)")
        self._pcc_next.setStyleSheet(
            "QPlainTextEdit{background:#1e1e1e;color:#cccccc;"
            "border:1px solid #3c3c3c;border-radius:3px;padding:4px}"
        )
        lay.addWidget(self._pcc_next)

        # Done
        lay.addWidget(QLabel("Ukończone", styleSheet=_LBL_HEAD))
        self._pcc_done = QPlainTextEdit()
        self._pcc_done.setReadOnly(True)
        self._pcc_done.setFont(_FONT_MONO)
        self._pcc_done.setFixedHeight(130)
        self._pcc_done.setPlaceholderText("(brak)")
        self._pcc_done.setStyleSheet(
            "QPlainTextEdit{background:#1e1e1e;color:#98c379;"
            "border:1px solid #2a5a2a;border-radius:3px;padding:4px}"
        )
        lay.addWidget(self._pcc_done)

        # Session Log
        lay.addWidget(QLabel("Session Log", styleSheet=_LBL_HEAD))
        self._pcc_log = QPlainTextEdit()
        self._pcc_log.setReadOnly(True)
        self._pcc_log.setFont(_FONT_MONO)
        self._pcc_log.setFixedHeight(160)
        self._pcc_log.setPlaceholderText("(brak wpisow)")
        self._pcc_log.setStyleSheet(
            "QPlainTextEdit{background:#1a1a1a;color:#5c6370;"
            "border:1px solid #3c3c3c;border-radius:3px;padding:4px}"
        )
        lay.addWidget(self._pcc_log)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)
        return w

    # ---- Historia ------------------------------------------------------ #

    def _build_historia(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(QLabel("Historia bieżącej sesji:", styleSheet=_LBL_HEAD))
        top.addStretch()
        self._btn_hist_refresh = QPushButton("⟳")
        self._btn_hist_refresh.setFixedWidth(28)
        self._btn_hist_refresh.setStyleSheet(_BTN)
        top.addWidget(self._btn_hist_refresh)
        lay.addLayout(top)

        lay.addWidget(QLabel("Ostatnia wiadomość CC:", styleSheet=_LBL_KEY))
        self._last_msg = QPlainTextEdit()
        self._last_msg.setReadOnly(True)
        self._last_msg.setFont(_FONT_MONO)
        self._last_msg.setFixedHeight(72)
        self._last_msg.setPlaceholderText("—")
        lay.addWidget(self._last_msg)

        lay.addWidget(QLabel("Ostatnie wpisy transkryptu:", styleSheet=_LBL_KEY))
        self._transcript = QPlainTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setFont(_FONT_MONO)
        self._transcript.setPlaceholderText("—")
        lay.addWidget(self._transcript, stretch=1)
        return w

    # ---- Sesje --------------------------------------------------------- #

    def _build_sesje(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(QLabel("Historia sesji projektu:", styleSheet=_LBL_HEAD))
        top.addStretch()
        self._btn_sesje_refresh = QPushButton("⟳")
        self._btn_sesje_refresh.setFixedWidth(28)
        self._btn_sesje_refresh.setStyleSheet(_BTN)
        top.addWidget(self._btn_sesje_refresh)
        lay.addLayout(top)

        sum_card = QFrame()
        sum_card.setStyleSheet(_CARD)
        sum_lay = QVBoxLayout(sum_card)
        sum_lay.setContentsMargins(8, 6, 8, 6)
        sum_lay.setSpacing(2)
        self._lbl_cc_sessions = _val()
        self._lbl_cc_last = _val()
        sum_lay.addLayout(_kv_row("Sesje CC (pliki):", self._lbl_cc_sessions))
        sum_lay.addLayout(_kv_row("Ostatnia CC:", self._lbl_cc_last))
        lay.addWidget(sum_card)
        lay.addStretch()
        return w

    # ---- Vibe Code ----------------------------------------------------- #

    def _build_vibe(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        lay.addWidget(QLabel(
            "Prompt wklejany do terminala CC przy uruchomieniu sesji:",
            styleSheet=_LBL_KEY,
            wordWrap=True,
        ))
        self._vibe_edit = QPlainTextEdit()
        self._vibe_edit.setFont(_FONT_MONO)
        self._vibe_edit.setPlaceholderText(DEFAULT_VIBE_PROMPT)
        lay.addWidget(self._vibe_edit, stretch=1)

        btns = QHBoxLayout()
        btn_reset = QPushButton("Resetuj do domyślnego")
        btn_reset.setStyleSheet(_BTN)
        btn_reset.clicked.connect(lambda: self._vibe_edit.setPlainText(DEFAULT_VIBE_PROMPT))
        btn_copy = QPushButton("Kopiuj do schowka")
        btn_copy.setStyleSheet(_BTN)
        btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self._vibe_edit.toPlainText())
        )
        btns.addWidget(btn_reset)
        btns.addWidget(btn_copy)
        btns.addStretch()
        lay.addLayout(btns)
        return w

    # ---- Historia + Sesje + Vibe Code (połączona zakładka) ------------ #

    def _build_historia_sesje_vibe(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_historia())
        splitter.addWidget(self._build_sesje())
        splitter.addWidget(self._build_vibe())
        splitter.setSizes([200, 220, 160])
        outer.addWidget(splitter)
        return w

    # ---- Pasek akcji --------------------------------------------------- #

    def _build_action_bar(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        self._btn_launch = QPushButton("▶  Start CC")
        self._btn_launch.setStyleSheet(_BTN_ACCENT)
        self._btn_launch.setFont(_FONT_MONO)
        self._btn_launch.setToolTip(
            "Otwórz VS Code z projektem i uruchom N terminali CC przez cc-panel"
        )

        self._btn_window = QPushButton("OKNO")
        self._btn_window.setStyleSheet(_BTN_GREEN)
        self._btn_window.setFont(_FONT_MONO)
        self._btn_window.setToolTip("Otwórz nowe okno VS Code z projektem")

        self._btn_push = QPushButton("↑ Push")
        self._btn_push.setStyleSheet(_BTN)
        self._btn_push.setFont(_FONT_MONO)
        self._btn_push.setToolTip("git add -A + commit + push")

        self._btn_round = QPushButton("⟳ Runda")
        self._btn_round.setStyleSheet(_BTN_GREEN)
        self._btn_round.setFont(_FONT_MONO)
        self._btn_round.setToolTip("Zakoncz runde: wyczys PLAN.md (Done/Current) + push")

        self._btn_stop = QPushButton("KONIEC")
        self._btn_stop.setStyleSheet(_BTN_DANGER)
        self._btn_stop.setFont(_FONT_MONO)
        self._btn_stop.setToolTip("Zatrzymaj sesje Auto-Accept CC")

        row.addWidget(self._btn_launch, stretch=2)
        row.addWidget(self._btn_window)
        row.addWidget(self._btn_push)
        row.addWidget(self._btn_round)
        row.addWidget(self._btn_stop)
        return w

    # ------------------------------------------------------------------ #
    # Sygnały                                                               #
    # ------------------------------------------------------------------ #

    _TAB_ZADANIOWIEC = 2  # indeks zakładki ZADANIOWIEC w self._tabs

    def _connect_signals(self) -> None:
        self._btn_launch.clicked.connect(lambda: self.launch_requested.emit(self._slot_id))
        self._btn_window.clicked.connect(lambda: self.window_requested.emit(self._slot_id))
        self._btn_push.clicked.connect(self._on_push)
        self._btn_round.clicked.connect(self._on_round_end)
        self._btn_stop.clicked.connect(lambda: self.stop_requested.emit(self._slot_id))
        self._btn_browse.clicked.connect(self._on_browse)
        self._btn_plan_refresh.clicked.connect(self.reload_plan)
        self._btn_plan_save.clicked.connect(self._on_plan_save)
        self._btn_hist_refresh.clicked.connect(self._refresh_transcript)
        self._btn_stats_refresh.clicked.connect(self.reload_stats)
        self._btn_sesje_refresh.clicked.connect(self.reload_history)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._vibe_edit.textChanged,
        ):
            sig.connect(self._on_config_changed)
        self._plan_editor.textChanged.connect(lambda: self._btn_plan_save.setEnabled(True))

    def _on_tab_changed(self, index: int) -> None:
        if index == self._TAB_ZADANIOWIEC:
            self.reload_zadaniowiec()

    # ------------------------------------------------------------------ #
    # Publiczne API                                                         #
    # ------------------------------------------------------------------ #

    def update_snapshot(self, snap: TerminalSnapshot) -> None:
        self._status_bar.refresh(snap)
        self._lbl_phase.setText(snap.phase or "—")
        self._lbl_model_live.setText(snap.model or "—")
        self._lbl_cost.setText(f"${snap.cost_usd:.4f}" if snap.cost_usd is not None else "—")
        self._lbl_ctx.setText(f"{snap.ctx_pct:.1f}%" if snap.ctx_pct is not None else "—")
        self._last_msg.setPlainText(snap.last_message or "—")
        if snap.transcript_path and not snap.is_file_missing:
            self._show_transcript(snap.transcript_path)

    def get_config(self) -> SlotConfig:
        return SlotConfig(
            project_path=self._path_edit.toPlainText().strip(),
            model=self._model_combo.currentText(),
            effort=self._effort_combo.currentText(),
            permission_mode=self._perm_combo.currentText(),
            vibe_prompt=self._vibe_edit.toPlainText() or DEFAULT_VIBE_PROMPT,
        )

    def reload_plan(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if not path:
            self._plan_editor.setPlainText("")
            self._lbl_plan_path.setText("(brak ścieżki)")
            return
        self._plan_data = read_plan(path)
        self._lbl_plan_path.setText(str(Path(path) / "PLAN.md"))
        self._render_plan()

    def reload_zadaniowiec(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if path:
            self._zadaniowiec.load_from_project(path, silent=True)

    def reload_pcc(self) -> None:
        path = self._path_edit.toPlainText().strip()
        plan_path = Path(path) / "PLAN.md" if path else None
        self._pcc_path_lbl.setText(str(plan_path) if plan_path else "")
        if not plan_path or not plan_path.exists():
            self._pcc_status.setText("—")
            self._pcc_goal.setText("—")
            self._pcc_session.setText("—")
            self._pcc_updated.setText("—")
            self._pcc_cur_task.setText("—")
            self._pcc_cur_file.setText("—")
            self._pcc_cur_started.setText("—")
            self._pcc_next.setPlainText("")
            self._pcc_done.setPlainText("")
            self._pcc_log.setPlainText("")
            return
        self._render_pcc(plan_path)

    def _render_pcc(self, plan_path: Path) -> None:
        try:
            text = plan_path.read_text(encoding="utf-8")
        except OSError:
            return

        meta = parse_dict(read_section(text, "meta") or "")
        current = parse_dict(read_section(text, "current") or "")
        next_items = parse_list(read_section(text, "next") or "")
        done_items = parse_list(read_section(text, "done") or "")
        log_body = read_section(text, "session_log") or ""

        # Meta
        status = meta.get("status", "—")
        if status == "active":
            self._pcc_status.setText("● active")
            self._pcc_status.setStyleSheet("color:#98c379;font-weight:bold;font-size:10px;")
        elif status == "idle":
            self._pcc_status.setText("◌ idle")
            self._pcc_status.setStyleSheet("color:#5c6370;font-weight:bold;font-size:10px;")
        else:
            self._pcc_status.setText(status or "—")
            self._pcc_status.setStyleSheet(_LBL_VAL)
        self._pcc_goal.setText(meta.get("goal", "—") or "—")
        self._pcc_session.setText(meta.get("session", "—"))
        self._pcc_updated.setText(meta.get("updated", "—"))

        # Current
        self._pcc_cur_task.setText(current.get("task", "—") or "(brak aktywnego)")
        self._pcc_cur_file.setText(current.get("file", "—") or "—")
        self._pcc_cur_started.setText(current.get("started", "—") or "—")

        # Next
        if next_items:
            lines = [f"[ ] {it['text']}" for it in next_items if not it.get("done")]
            self._pcc_next.setPlainText("\n".join(lines))
        else:
            self._pcc_next.setPlainText("")

        # Done
        if done_items:
            lines = []
            for it in reversed(done_items):
                date = f"  @ {it['date']}" if it.get("date") else ""
                lines.append(f"[x] {it['text']}{date}")
            self._pcc_done.setPlainText("\n".join(lines))
        else:
            self._pcc_done.setPlainText("")

        # Session Log
        log_lines = [l.strip() for l in log_body.splitlines() if l.strip()]
        self._pcc_log.setPlainText("\n".join(reversed(log_lines)) if log_lines else "")

    def reload_md_files(self) -> None:
        """Odświeża zakładki CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md."""
        for filename in ("CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md"):
            self._reload_md_file(filename)

    def reload_stats(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if not path:
            return
        self._stats = get_project_stats(path)
        self._render_stats()

    def reload_history(self) -> None:
        path = self._path_edit.toPlainText().strip()
        self._history = get_session_history(
            terminal_id=self._slot_id,
            project_path=path,
        )
        self._render_history()

    # ------------------------------------------------------------------ #
    # Prywatne                                                              #
    # ------------------------------------------------------------------ #

    def _load_config(self) -> None:
        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._vibe_edit.textChanged,
        ):
            sig.disconnect(self._on_config_changed)

        self._path_edit.setPlainText(self._config.project_path)
        idx = self._model_combo.findText(self._config.model)
        self._model_combo.setCurrentIndex(max(0, idx))
        idx = self._effort_combo.findText(self._config.effort)
        self._effort_combo.setCurrentIndex(max(0, idx))
        idx = self._perm_combo.findText(self._config.permission_mode)
        self._perm_combo.setCurrentIndex(max(0, idx))
        self._vibe_edit.setPlainText(self._config.vibe_prompt)

        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._vibe_edit.textChanged,
        ):
            sig.connect(self._on_config_changed)

        if self._config.project_path:
            self._lbl_plan_path.setText(
                str(Path(self._config.project_path) / "PLAN.md")
            )
            self.reload_plan()
            self.reload_pcc()
            self.reload_stats()
            self.reload_history()
            self.reload_md_files()

    def _on_config_changed(self) -> None:
        self._save_timer.start(800)

    def _on_debounce(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if path:
            self._lbl_plan_path.setText(str(Path(path) / "PLAN.md"))
            if not self._plan_data or self._plan_data.is_missing:
                self.reload_plan()
            if not self._stats:
                self.reload_stats()
        self.config_changed.emit()

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Wybierz katalog projektu",
            self._path_edit.toPlainText().strip() or str(Path.home()),
        )
        if folder:
            self._path_edit.setPlainText(folder)
            self.reload_plan()
            self.reload_pcc()
            self.reload_stats()
            self.reload_history()
            self.reload_md_files()
            self.reload_zadaniowiec()

    def _on_plan_save(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if not path:
            return
        if self._plan_data is None:
            self._plan_data = PlanData(raw_text=self._plan_editor.toPlainText())
        else:
            self._plan_data.raw_text = self._plan_editor.toPlainText()
        if write_plan(path, self._plan_data):
            self._btn_plan_save.setEnabled(False)
            self._plan_data = read_plan(path)
            self._render_plan()

    def _render_plan(self) -> None:
        if not self._plan_data:
            return
        if self._plan_data.is_missing:
            self._plan_editor.setPlainText("")
            self._plan_editor.setPlaceholderText("Brak PLAN.md w katalogu projektu.")
            self._lbl_plan_stan.setText("Stan: —")
            self._lbl_plan_active.setText("Aktywne: —")
            self._btn_plan_save.setEnabled(False)
            return
        self._plan_editor.blockSignals(True)
        self._plan_editor.setPlainText(self._plan_data.raw_text)
        self._plan_editor.blockSignals(False)
        self._btn_plan_save.setEnabled(False)
        stan = get_section(self._plan_data, "Stan") or "—"
        active = (get_section(self._plan_data, "Aktywne zadanie") or "—").replace("\n", " ")
        self._lbl_plan_stan.setText(f"Stan: {stan[:80]}")
        self._lbl_plan_active.setText(f"Aktywne: {active[:120]}")

    def _render_stats(self) -> None:
        s = self._stats
        if not s:
            return
        if s.error:
            self._lbl_files.setText(s.error)
            self._lbl_files.setStyleSheet(_LBL_ERR)
            return
        self._lbl_files.setText(f"{s.file_count} plików · {s.folder_count} folderów")
        self._lbl_files.setStyleSheet(_LBL_VAL)
        self._lbl_size.setText(fmt_size(s.disk_usage_bytes))
        if s.has_git:
            self._lbl_git.setText("✓ tak")
            self._lbl_git.setStyleSheet(_LBL_OK)
        else:
            self._lbl_git.setText("✗ brak")
            self._lbl_git.setStyleSheet(_LBL_WARN)
        self._lbl_git_url.setText(s.git_remote_url or "—")
        self._lbl_git_url.setToolTip(s.git_remote_url)
        self._lbl_branch.setText(s.git_branch or "—")

        from src.cc_launcher.project_stats import KEY_FILES
        for fname in KEY_FILES:
            lbl = self._key_file_labels[fname]
            if fname in s.key_file_sizes:
                lbl.setText(fmt_size(s.key_file_sizes[fname]))
                lbl.setStyleSheet(_LBL_VAL)
            else:
                lbl.setText("brak")
                lbl.setStyleSheet(_LBL_DIM)

    def _render_history(self) -> None:
        h = self._history
        if not h:
            return
        # Regularne sesje CC
        self._lbl_cc_sessions.setText(
            f"{h.transcript_count} sesji" if h.transcript_count else "0"
        )
        if h.transcript_last_at:
            self._lbl_cc_last.setText(
                h.transcript_last_at.strftime("%Y-%m-%d %H:%M")
            )
        else:
            self._lbl_cc_last.setText("—")


    def stop_with_round_end(self) -> None:
        """Uruchamia round_end, po zakonczeniu terminuje sesje CC."""
        path = self._path_edit.toPlainText().strip()
        if not path:
            terminate_vscode_session(self._slot_id)
            self.stop_completed.emit(self._slot_id)
            return
        self._stop_pending = True
        self._btn_round.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._workflow.run_round_end(path)

    def _on_push(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if not path:
            return
        if not Path(path).is_dir():
            QMessageBox.warning(self, "Push Git", f"Katalog projektu nie istnieje:\n{path}")
            return
        if not (Path(path) / ".git").exists():
            self._show_git_init_dialog(path)
            return
        self._btn_push.setEnabled(False)
        self._workflow.run_git_push(path)

    def _show_git_init_dialog(self, path: str) -> None:
        dlg = GitInitDialog(path, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._btn_push.setEnabled(False)
        self._workflow.run_git_init(
            project_path=path,
            remote_url=dlg.remote_url,
            branch=dlg.branch,
            commit_message=dlg.commit_message,
        )

    def _on_round_end(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if not path:
            return
        reply = QMessageBox.question(
            self,
            "Zakoncz runde",
            "Wyczyscic PLAN.md (Done + Current) i wyslac zmiany na git?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._btn_round.setEnabled(False)
            self._workflow.run_round_end(path)

    def _on_workflow_done(self, name: str, ok: bool, msg: str) -> None:
        self._btn_push.setEnabled(True)
        self._btn_round.setEnabled(True)
        self._btn_stop.setEnabled(True)
        if name in ("round_end", "clean_plan") and ok:
            self.reload_plan()
            self.reload_pcc()
        if name == "git_init" and ok:
            self.reload_stats()

        if name == "round_end" and self._stop_pending:
            self._stop_pending = False
            if not ok:
                QMessageBox.warning(
                    self, "Zakoncz sesje",
                    f"round_end nie powiodl sie:\n{msg}\n\nSesja zostanie zatrzymana.",
                )
            terminate_vscode_session(self._slot_id)
            self.stop_completed.emit(self._slot_id)
            return

        titles = {
            "clean_plan": "Wyczys PLAN",
            "git_push": "Push Git",
            "git_init": "Inicjalizacja Git",
            "round_end": "Zakoncz runde",
        }
        title = titles.get(name, name)
        if ok:
            QMessageBox.information(self, title, msg or "OK")
        else:
            QMessageBox.critical(self, title, msg or "Blad operacji")

    def _refresh_transcript(self) -> None:
        # Znajdź snapshot przez rodzica
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, CCLauncherPanel):
                snap = parent._watcher.get_snapshot(self._slot_id)
                if snap.transcript_path:
                    self._show_transcript(snap.transcript_path)
                return
            parent = parent.parent()

    def _show_transcript(self, path: str) -> None:
        entries = read_transcript_tail(path, n_messages=5)
        if not entries:
            self._transcript.setPlainText("(brak wpisów)")
            return
        lines = []
        for e in entries:
            role = "USER" if e["type"] == "user" else "  CC"
            text = e["text"].replace("\n", " ").strip()
            lines.append(f"[{role}] {text[:220]}")
        self._transcript.setPlainText("\n\n".join(lines))


class _TerminalCountSelector(QWidget):
    """Segmented control 1-4 — drop-in replacement dla QSpinBox(1, 4).

    Cztery toggleable buttons (radio-like): klik wybiera ile terminali CC ma się
    uruchomić dla tego slotu. Aktywny przycisk barwi się kolorem slotu.
    Wystawia API zgodne z QSpinBox: value(), setValue(), valueChanged(int).
    """

    valueChanged = Signal(int)

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 1
        self._color = color
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._buttons: list[QPushButton] = []
        for n in range(1, 5):
            btn = QPushButton(str(n))
            btn.setCheckable(True)
            btn.setFixedSize(34, 28)
            btn.setStyleSheet(self._btn_style())
            btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            btn.clicked.connect(lambda _checked, k=n: self.setValue(k))
            self._buttons.append(btn)
            lay.addWidget(btn)
        self._buttons[0].setChecked(True)

    def _btn_style(self) -> str:
        c = self._color
        return (
            f"QPushButton{{background:#2d2d2d;color:#aaaaaa;"
            f"border:1px solid #454545;border-radius:3px;}}"
            f"QPushButton:hover{{background:{c}40;color:#ffffff;border-color:{c};}}"
            f"QPushButton:checked{{background:{c};color:#000000;border-color:{c};}}"
        )

    def value(self) -> int:
        return self._value

    def setValue(self, n: int) -> None:
        n = max(1, min(4, int(n)))
        changed = (n != self._value)
        self._value = n
        for i, btn in enumerate(self._buttons, start=1):
            btn.blockSignals(True)
            btn.setChecked(i == n)
            btn.blockSignals(False)
        if changed:
            self.valueChanged.emit(n)


class _ColoredSlotTabBar(QTabBar):
    """QTabBar z kolorowym tłem per indeks i dwuwierszową etykietą (Projekt N + folder).

    Qt nie pozwala stylować pojedynczych zakładek przez QSS, więc rysujemy własnym
    paintEvent. Każda zakładka dostaje barwę z `colors[i]`: pełną dla aktywnej,
    półprzezroczystą dla hovera, mocno przyciemnioną dla nieaktywnej.
    """

    def __init__(self, colors: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors = [QColor(c) for c in colors]
        self._sub_labels: list[str] = ["", "", "", ""]
        self._hover_index = -1
        self.setMouseTracking(True)
        self.setExpanding(False)
        self.setDrawBase(False)

    def setSubLabel(self, index: int, text: str) -> None:
        if 0 <= index < len(self._sub_labels):
            self._sub_labels[index] = text or ""
            self.update()

    def tabSizeHint(self, index: int) -> QSize:  # type: ignore[override]
        return QSize(200, 56)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        super().mouseMoveEvent(event)
        try:
            point = event.position().toPoint()
        except AttributeError:
            point = event.pos()
        idx = self.tabAt(point)
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        super().leaveEvent(event)
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for i in range(self.count()):
            color = self._colors[i] if i < len(self._colors) else QColor("#888888")
            rect = self.tabRect(i)
            is_selected = (i == self.currentIndex())
            is_hover = (i == self._hover_index)

            bg = QColor(color)
            if is_selected:
                pass
            elif is_hover:
                bg.setAlpha(150)
            else:
                bg.setAlpha(70)
            painter.fillRect(rect, bg)

            if is_selected:
                indicator = QRect(rect.x(), rect.bottom() - 3, rect.width(), 3)
                painter.fillRect(indicator, color.lighter(135))

            main_text = self.tabText(i) or ""
            sub_text = self._sub_labels[i] if i < len(self._sub_labels) else ""

            if sub_text:
                main_rect = QRect(rect.x() + 4, rect.y() + 4,
                                  rect.width() - 8, rect.height() // 2 - 2)
                sub_rect = QRect(rect.x() + 4, rect.y() + rect.height() // 2,
                                 rect.width() - 8, rect.height() // 2 - 5)

                font_main = QFont("Segoe UI", 11)
                font_main.setBold(True)
                painter.setFont(font_main)
                painter.setPen(QColor("#000000") if is_selected else color.lighter(170))
                painter.drawText(main_rect, Qt.AlignmentFlag.AlignCenter, main_text)

                font_sub = QFont("Segoe UI", 9)
                painter.setFont(font_sub)
                painter.setPen(QColor("#1a1a1a") if is_selected else color)
                metrics = painter.fontMetrics()
                elided = metrics.elidedText(sub_text, Qt.TextElideMode.ElideMiddle, rect.width() - 12)
                painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, elided)
            else:
                font_main = QFont("Segoe UI", 11)
                font_main.setBold(True)
                painter.setFont(font_main)
                painter.setPen(QColor("#000000") if is_selected else color.lighter(170))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, main_text)


class CCLauncherPanel(QWidget):
    """Główny panel 'Sesje CC' z 4 zakładkami slotów projektów."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = load_launcher_config()
        self._watcher = SessionWatcher(parent=self)
        self._slots: list[ProjectSlotWidget] = []

        self._setup_ui()
        self._connect_signals()
        self._watcher.start()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        root.addWidget(self._build_header())

        self._slot_tabs = QTabWidget()
        self._slot_tab_bar = _ColoredSlotTabBar(SLOT_COLORS)
        self._slot_tabs.setTabBar(self._slot_tab_bar)
        for i in range(4):
            slot = ProjectSlotWidget(i + 1, self._config.slots[i], parent=self)
            self._slots.append(slot)
            self._slot_tabs.addTab(slot, SLOT_NAMES[i])
            path = self._config.slots[i].project_path
            self._slot_tab_bar.setSubLabel(i, Path(path).name if path else "—")
        root.addWidget(self._slot_tabs, stretch=1)

    def _build_header(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(12)

        title = QLabel("Sesje Claude Code")
        title.setStyleSheet("color:#cccccc;font-size:13px;font-weight:bold;")
        row.addWidget(title)

        # Globalny selektor liczby terminali (wspólny dla wszystkich slotów)
        row.addWidget(QLabel("Terminale CC:", styleSheet=_LBL_KEY))
        self._term_selector = _TerminalCountSelector("#4da6ff")
        self._term_selector.setValue(self._config.terminal_count)
        self._term_selector.valueChanged.connect(self._on_global_term_changed)
        row.addWidget(self._term_selector)

        row.addStretch()
        row.addWidget(QLabel("polling co 15s", styleSheet=_LBL_DIM))
        btn = QPushButton("⟳  Odśwież")
        btn.setStyleSheet(_BTN)
        btn.setFont(_FONT_MONO)
        btn.clicked.connect(self._watcher.force_refresh)
        row.addWidget(btn)
        return w

    def _on_global_term_changed(self, n: int) -> None:
        self._config.terminal_count = max(1, min(4, int(n)))
        save_launcher_config(self._config)

    def _connect_signals(self) -> None:
        self._watcher.snapshot_updated.connect(self._on_snapshot)
        for slot in self._slots:
            slot.config_changed.connect(self._on_config_changed)
            slot.launch_requested.connect(self._on_launch)
            slot.window_requested.connect(self._on_window)
            slot.stop_requested.connect(self._on_stop)
            slot.stop_completed.connect(self._on_stop_completed)

    def _on_snapshot(self, snap: TerminalSnapshot) -> None:
        self._slots[snap.slot_id - 1].update_snapshot(snap)

    def _on_config_changed(self) -> None:
        for i, slot in enumerate(self._slots):
            self._config.slots[i] = slot.get_config()
            path = self._config.slots[i].project_path
            self._slot_tab_bar.setSubLabel(i, Path(path).name if path else "—")
        save_launcher_config(self._config)

    def assign_project(self, path: Path) -> int:
        """Assign a new project path to the first empty slot (or slot 1 as fallback).

        Returns the 1-based slot number that received the project.
        Switches the tab to that slot automatically.
        """
        from pathlib import Path as _Path
        target = 1
        for i, slot in enumerate(self._slots):
            if not slot.get_config().project_path.strip():
                target = i + 1
                break

        slot_widget = self._slots[target - 1]
        slot_widget._path_edit.setPlainText(str(path))
        slot_widget.reload_plan()
        slot_widget.reload_stats()
        slot_widget.reload_md_files()
        self._slot_tabs.setCurrentIndex(target - 1)
        return target

    def _on_launch(self, slot_id: int) -> None:
        cfg = self._config.slots[slot_id - 1]
        if not cfg.project_path:
            QMessageBox.warning(
                self, "CC Launcher",
                f"Slot {slot_id}: Nie ustawiono ścieżki projektu.",
            )
            return
        if not Path(cfg.project_path).is_dir():
            QMessageBox.warning(
                self, "CC Launcher",
                f"Ścieżka nie istnieje:\n{cfg.project_path}",
            )
            return

        ok = prepare_and_launch(
            slot_id=slot_id,
            project_path=cfg.project_path,
            terminal_count=self._config.terminal_count,
            vibe_prompt=cfg.vibe_prompt,
        )
        if not ok:
            QMessageBox.critical(
                self, "CC Launcher",
                "Nie udało się uruchomić VS Code.\n"
                "Sprawdź czy komenda 'code' jest dostępna w PATH.",
            )
            return

        # Odśwież stan po ~25s (CC potrzebuje czasu na załadowanie)
        QTimer.singleShot(25_000, self._watcher.force_refresh)

    def _on_window(self, slot_id: int) -> None:
        cfg = self._config.slots[slot_id - 1]
        open_vscode_window(cfg.project_path)

    def _on_stop(self, slot_id: int) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Zakoncz sesje CC — Slot {slot_id}")
        msg.setText("Jak chcesz zakonczyc sesje?")
        msg.setInformativeText(
            "Zakoncz + Runda: wyczysci PLAN.md i wypchnnie zmiany na git przed zamknieciem.\n"
            "Tylko zakoncz: zatrzymuje sesje natychmiast."
        )
        btn_runda = msg.addButton("Zakoncz + Runda", QMessageBox.ButtonRole.AcceptRole)
        btn_stop = msg.addButton("Tylko zakoncz", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Anuluj", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is btn_runda:
            self._slots[slot_id - 1].stop_with_round_end()
        elif clicked is btn_stop:
            terminate_vscode_session(slot_id)
            QTimer.singleShot(1000, self._watcher.force_refresh)

    def _on_stop_completed(self, slot_id: int) -> None:
        QTimer.singleShot(1000, self._watcher.force_refresh)


def _wrap(layout: QHBoxLayout) -> QWidget:
    """Owija QHBoxLayout w QWidget do użycia w _kv_row."""
    w = QWidget()
    w.setLayout(layout)
    return w
