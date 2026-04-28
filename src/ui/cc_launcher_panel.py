"""Panel 'Sesje CC' — uruchamianie i monitorowanie sesji Claude Code."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QProcess, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCursor
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
    QTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
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
    find_latest_transcript,
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

# SSS Module — lazy import żeby nie blokować startu CM jeśli moduł nie istnieje
try:
    from SSS.src.cm.sss_module.views.intake_view import IntakeView as _SSSIntakeView
    from SSS.src.cm.sss_module.views.logs_view import LogsView as _SSSLogsView
    from SSS.src.cm.sss_module.core.log_store import LogStore as _SSSLogStore
    from SSS.src.cm.sss_module.core.spawner import ProjectSpawner as _SSSSpawner
    from SSS.src.cm.sss_module.core.plan_watcher import PlanWatcher as _SSSPlanWatcher
    from SSS.src.cm.sss_module.core.round_watcher import RoundWatcher as _SSSRoundWatcher
    _SSS_AVAILABLE = True
except ImportError:
    _SSS_AVAILABLE = False
from src.watchers.session_watcher import (
    SessionWatcher,
    TerminalSnapshot,
    read_transcript_messages,
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


# ── Stałe dla konwersji DPS ──────────────────────────────────────────────────

# Kanoniczne nazwy plików w projekcie DPS i ich aliasy (małe litery → kanon)
_DPS_CANON: dict[str, str] = {
    "claude.md":       "CLAUDE.md",
    "architecture.md": "ARCHITECTURE.md",
    "conventions.md":  "CONVENTIONS.md",
    "plan.md":         "PLAN.md",
    "readme.md":       "README.md",
    "roadmap.md":      "ROADMAP.md",
}

# Które pliki konwertujemy sekcjami (pozostałe tylko rename)
_DPS_CONVERTIBLE = {"CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md"}

# Pliki rozpoznawane ale pomijane przy konwersji i rename (tylko informacyjnie)
_DPS_READONLY = {"README.md", "ROADMAP.md"}

_DPS_GEN_PROMPT: dict[str, str] = {
    "CLAUDE.md": (
        "Jesteś ekspertem od dokumentacji projektów programistycznych.\n"
        "Wygeneruj plik CLAUDE.md dla projektu na podstawie poniższego kontekstu.\n\n"
        "CLAUDE.md to instrukcja dla asystenta AI (Claude Code) — zawiera:\n"
        "opis projektu, stack technologiczny, zasady kodowania, komendy uruchomienia,\n"
        "strukturę katalogów i wszelkie konwencje których AI ma przestrzegać.\n\n"
        "Format wyjściowy — format DPS z sekcjami:\n"
        "## Nazwa sekcji\n"
        "<!-- SECTION:slug -->\n"
        "treść\n"
        "<!-- /SECTION:slug -->\n\n"
        "Użyj slugów: overview, stack, commands, structure, rules, conventions\n\n"
        "Odpowiedz WYŁĄCZNIE treścią pliku CLAUDE.md — zero komentarzy, zero wyjaśnień.\n\n"
        "Kontekst projektu (istniejące pliki):\n{context}"
    ),
    "ARCHITECTURE.md": (
        "Jesteś ekspertem od dokumentacji projektów programistycznych.\n"
        "Wygeneruj plik ARCHITECTURE.md dla projektu na podstawie poniższego kontekstu.\n\n"
        "ARCHITECTURE.md opisuje strukturę techniczną projektu — moduły, warstwy,\n"
        "przepływ danych, zależności między komponentami i decyzje architektoniczne.\n\n"
        "Format wyjściowy — format DPS z sekcjami:\n"
        "## Nazwa sekcji\n"
        "<!-- SECTION:slug -->\n"
        "treść\n"
        "<!-- /SECTION:slug -->\n\n"
        "Użyj slugów: overview, structure, modules, data_flow, dependencies, decisions\n\n"
        "Odpowiedz WYŁĄCZNIE treścią pliku ARCHITECTURE.md — zero komentarzy, zero wyjaśnień.\n\n"
        "Kontekst projektu (istniejące pliki):\n{context}"
    ),
    "CONVENTIONS.md": (
        "Jesteś ekspertem od dokumentacji projektów programistycznych.\n"
        "Wygeneruj plik CONVENTIONS.md dla projektu na podstawie poniższego kontekstu.\n\n"
        "CONVENTIONS.md zawiera konwencje zespołowe — nazewnictwo, formatowanie kodu,\n"
        "zasady git (branche, commity), standardy testowania, importy, komentarze.\n"
        "Wywnioskuj konwencje z istniejących plików projektu lub zaproponuj ogólnie przyjęte.\n\n"
        "Format wyjściowy — format DPS z sekcjami:\n"
        "## Nazwa sekcji\n"
        "<!-- SECTION:slug -->\n"
        "treść\n"
        "<!-- /SECTION:slug -->\n\n"
        "Użyj slugów: naming, formatting, git, testing, imports, comments\n\n"
        "Odpowiedz WYŁĄCZNIE treścią pliku CONVENTIONS.md — zero komentarzy, zero wyjaśnień.\n\n"
        "Kontekst projektu (istniejące pliki):\n{context}"
    ),
}

_DPS_CONV_PROMPT: dict[str, str] = {
    "CLAUDE.md": (
        "Jesteś narzędziem do konwersji plików CLAUDE.md.\n"
        "Przepisz podany plik do formatu DPS, w którym każda logiczna sekcja\n"
        "jest opakowana w znaczniki:\n"
        "<!-- SECTION:nazwa -->\n"
        "treść sekcji\n"
        "<!-- /SECTION:nazwa -->\n\n"
        "Zasady:\n"
        "- Zachowaj CAŁĄ oryginalną treść bez zmian sensu\n"
        "- Nagłówki ## pozostaw na miejscu; wstaw SECTION bezpośrednio pod nagłówkiem\n"
        "- Nazwa sekcji to slug angielski bez spacji (np. stack, commands, rules, goals)\n"
        "- Sekcje zagnieżdżone (###) wchodzą do sekcji nadrzędnej (##)\n"
        "- Odpowiedz WYŁĄCZNIE treścią skonwertowanego pliku — zero komentarzy,\n"
        "  zero bloków markdown, zero wyjaśnień przed ani po\n\n"
        "Plik CLAUDE.md do skonwertowania:\n\n{content}"
    ),
    "ARCHITECTURE.md": (
        "Jesteś narzędziem do konwersji plików ARCHITECTURE.md.\n"
        "Przepisz podany plik do formatu DPS, w którym każda logiczna sekcja\n"
        "jest opakowana w znaczniki:\n"
        "<!-- SECTION:nazwa -->\n"
        "treść sekcji\n"
        "<!-- /SECTION:nazwa -->\n\n"
        "Zasady:\n"
        "- Zachowaj CAŁĄ oryginalną treść bez zmian sensu\n"
        "- Nagłówki ## pozostaw na miejscu; wstaw SECTION bezpośrednio pod nagłówkiem\n"
        "- Nazwa sekcji to slug angielski opisujący architekturę\n"
        "  (np. overview, structure, modules, data_flow, dependencies)\n"
        "- Sekcje zagnieżdżone (###) wchodzą do sekcji nadrzędnej (##)\n"
        "- Odpowiedz WYŁĄCZNIE treścią skonwertowanego pliku — zero komentarzy,\n"
        "  zero bloków markdown, zero wyjaśnień przed ani po\n\n"
        "Plik ARCHITECTURE.md do skonwertowania:\n\n{content}"
    ),
    "CONVENTIONS.md": (
        "Jesteś narzędziem do konwersji plików CONVENTIONS.md.\n"
        "Przepisz podany plik do formatu DPS, w którym każda logiczna sekcja\n"
        "jest opakowana w znaczniki:\n"
        "<!-- SECTION:nazwa -->\n"
        "treść sekcji\n"
        "<!-- /SECTION:nazwa -->\n\n"
        "Zasady:\n"
        "- Zachowaj CAŁĄ oryginalną treść bez zmian sensu\n"
        "- Nagłówki ## pozostaw na miejscu; wstaw SECTION bezpośrednio pod nagłówkiem\n"
        "- Nazwa sekcji to slug angielski opisujący konwencje\n"
        "  (np. naming, formatting, git, testing, imports, comments)\n"
        "- Sekcje zagnieżdżone (###) wchodzą do sekcji nadrzędnej (##)\n"
        "- Odpowiedz WYŁĄCZNIE treścią skonwertowanego pliku — zero komentarzy,\n"
        "  zero bloków markdown, zero wyjaśnień przed ani po\n\n"
        "Plik CONVENTIONS.md do skonwertowania:\n\n{content}"
    ),
}


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
        self._git_init_then_round_end = False
        self._zadaniowiec_loaded = False
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

        self._tabs.addTab(self._build_historia_sesje_vibe(), "Sesje")
        self._tabs.addTab(self._build_dane(), "Dane")
        self._tabs.addTab(self._build_plan(), "ZADANIA")
        self._tabs.addTab(self._build_zadaniowiec(), "ZADANIOWIEC")
        self._tabs.addTab(self._build_sss(), "SSS")
        self._tabs.addTab(self._build_pcc(), "PLAN.md")
        self._tabs.addTab(self._build_md_file("CLAUDE.md"), "CLAUDE.md")
        self._tabs.addTab(self._build_md_file("ARCHITECTURE.md"), "ARCHITECTURE.md")
        self._tabs.addTab(self._build_md_file("CONVENTIONS.md"), "CONVENTIONS.md")
        self._tabs.addTab(self._build_logi(), "Logi")
        self._tabs.addTab(self._build_full_converter(), "Full Converter")

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

    # ---- SSS ----------------------------------------------------------- #

    def _build_sss(self) -> QWidget:
        if not _SSS_AVAILABLE:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.addWidget(QLabel("Moduł SSS niedostępny (błąd importu)."))
            return w

        db_path = Path.home() / ".claude" / "sss_events.db"
        self._sss_store = _SSSLogStore(db_path)
        self._sss_spawner = _SSSSpawner()
        self._sss_plan_watcher: "_SSSPlanWatcher | None" = None
        self._sss_round_watcher: "_SSSRoundWatcher | None" = None
        self._sss_active_session: str | None = None

        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._sss_intake = _SSSIntakeView()
        self._sss_intake.qt_start_clicked.connect(self._on_sss_start)
        splitter.addWidget(self._sss_intake)

        self._sss_logs = _SSSLogsView(self._sss_store)
        self._sss_logs.refresh_sessions()
        splitter.addWidget(self._sss_logs)
        splitter.setSizes([280, 320])

        root.addWidget(splitter)
        return w

    def _sss_start_watchers(self, project_dir: Path, session_id: str) -> None:
        if not _SSS_AVAILABLE:
            return
        self._sss_stop_watchers()
        self._sss_active_session = session_id

        plan_path = project_dir / "PLAN.md"
        self._sss_plan_watcher = _SSSPlanWatcher(plan_path, parent=self)
        self._sss_plan_watcher.qt_plan_changed.connect(self._on_sss_plan_changed)
        self._sss_plan_watcher.qt_plan_error.connect(
            lambda msg: self._sss_store.insert_event(session_id, "plan_error", payload={"error": msg})
        )

        self._sss_round_watcher = _SSSRoundWatcher(project_dir, parent=self)
        self._sss_round_watcher.qt_md_read.connect(
            lambda fname, _content: self._sss_store.insert_event(
                session_id, "md_read", file_path=fname
            )
        )
        self._sss_plan_watcher.qt_plan_changed.connect(self._sss_round_watcher.on_plan_changed)
        self._sss_plan_watcher.start()

    def _sss_stop_watchers(self) -> None:
        if self._sss_plan_watcher is not None:
            self._sss_plan_watcher.stop()
            self._sss_plan_watcher.deleteLater()
            self._sss_plan_watcher = None
        self._sss_round_watcher = None
        self._sss_active_session = None

    def _on_sss_start(self, prompt: str, project_name: str, location: str) -> None:
        try:
            session_id, project_dir = self._sss_spawner.spawn(prompt, project_name, Path(location))
            self._sss_store.insert_event(session_id, "spawn", payload={
                "project_name": project_name,
                "location": location,
                "prompt_preview": prompt[:120],
            })
            self._sss_logs.refresh_sessions()
            self._sss_start_watchers(project_dir, session_id)
        except Exception as exc:
            QMessageBox.critical(self, "SSS — błąd startu", str(exc))

    def _on_sss_plan_changed(self, sections: dict) -> None:
        if not self._sss_active_session:
            return
        current = sections.get("current", "")
        self._sss_store.insert_event(
            self._sss_active_session,
            "plan_change",
            payload={"current": current[:200]},
        )

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

        sizes = [420, 130]

        if filename in _DPS_CONVERTIBLE:
            # Stacked: 0 = konwerter (plik istnieje), 1 = generator (brak pliku)
            action_stack = QStackedWidget()
            action_stack.addWidget(self._build_md_converter(filename))
            action_stack.addWidget(self._build_md_generator(filename))
            splitter.addWidget(action_stack)
            sizes.append(260)
            setattr(self, f"_md_action_stack_{filename.replace('.', '_')}", action_stack)

        splitter.setSizes(sizes)
        root.addWidget(splitter, stretch=1)

        # Przechowaj referencje jako atrybuty slotu
        safe = filename.replace(".", "_")
        setattr(self, f"_md_path_lbl_{safe}", lbl_path)
        setattr(self, f"_md_sections_layout_{safe}", sections_layout)
        setattr(self, f"_md_changelog_view_{safe}", changelog_view)
        btn_refresh.clicked.connect(lambda: self._reload_md_file(filename))

        return w

    def _build_md_generator(self, filename: str) -> QWidget:
        """Panel generowania pliku MD od zera przez AI (widoczny gdy plik nie istnieje)."""
        safe = filename.replace(".", "_")

        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background:#0d1a12;border:1px solid #1a4a2a;border-radius:4px;}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel(f"Generuj {filename} od zera", styleSheet=_LBL_HEAD))
        hdr.addStretch()
        gen_badge = QLabel("")
        gen_badge.setVisible(False)
        hdr.addWidget(gen_badge)
        lay.addLayout(hdr)

        desc = QLabel(
            f"Plik {filename} nie istnieje w projekcie.\n"
            "AI wygeneruje go od zera na podstawie pozostałych plików MD projektu "
            "oraz ogólnie przyjętych standardów. Wynik pojawi się poniżej — "
            "sprawdź go przed zapisem."
        )
        desc.setStyleSheet("color:#6b7280;font-size:10px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addWidget(_sep())

        gen_output = QPlainTextEdit()
        gen_output.setReadOnly(True)
        gen_output.setFont(_FONT_MONO)
        gen_output.setFixedHeight(80)
        gen_output.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#61afef;"
            "border:1px solid #1a3a4a;border-radius:3px;padding:4px;}"
        )
        gen_output.setPlaceholderText(f"Tutaj pojawi się wygenerowana treść {filename}…")
        lay.addWidget(gen_output)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_gen_run = QPushButton("✦  Generuj przez AI")
        btn_gen_run.setStyleSheet(
            "QPushButton{background:#1a2a3a;color:#61afef;"
            "border:1px solid #2a4a6a;border-radius:3px;padding:5px 14px;font-weight:bold}"
            "QPushButton:hover{background:#2a4a6a}"
            "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
        )
        btn_row.addWidget(btn_gen_run)

        btn_gen_stop = QPushButton("■  Stop")
        btn_gen_stop.setStyleSheet(
            "QPushButton{background:#3a2a00;color:#e5c07b;"
            "border:1px solid #5a4000;border-radius:3px;padding:5px 12px}"
            "QPushButton:hover{background:#5a4000}"
        )
        btn_gen_stop.setEnabled(False)
        btn_row.addWidget(btn_gen_stop)

        btn_gen_save = QPushButton(f"→ Zapisz jako {filename}")
        btn_gen_save.setStyleSheet(_BTN_GREEN)
        btn_gen_save.setEnabled(False)
        btn_row.addWidget(btn_gen_save)

        btn_row.addStretch()
        gen_status = QLabel("", styleSheet=_LBL_DIM)
        gen_status.setFont(_FONT_SMALL)
        btn_row.addWidget(gen_status)
        lay.addLayout(btn_row)

        # Zapisz referencje
        setattr(self, f"_gen_output_{safe}", gen_output)
        setattr(self, f"_gen_btn_run_{safe}", btn_gen_run)
        setattr(self, f"_gen_btn_stop_{safe}", btn_gen_stop)
        setattr(self, f"_gen_btn_save_{safe}", btn_gen_save)
        setattr(self, f"_gen_status_{safe}", gen_status)
        setattr(self, f"_gen_badge_{safe}", gen_badge)
        setattr(self, f"_gen_process_{safe}", None)
        setattr(self, f"_gen_buffer_{safe}", "")

        btn_gen_run.clicked.connect(lambda: self._gen_run(filename))
        btn_gen_stop.clicked.connect(lambda: self._gen_stop(filename))
        btn_gen_save.clicked.connect(lambda: self._gen_save(filename))

        return frame

    def _gen_run(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        gen_output: QPlainTextEdit = getattr(self, f"_gen_output_{safe}")
        btn_run: QPushButton = getattr(self, f"_gen_btn_run_{safe}")
        btn_stop: QPushButton = getattr(self, f"_gen_btn_stop_{safe}")
        btn_save: QPushButton = getattr(self, f"_gen_btn_save_{safe}")
        status: QLabel = getattr(self, f"_gen_status_{safe}")

        project_path = self._path_edit.toPlainText().strip()
        if not project_path:
            status.setText("Brak ścieżki projektu")
            return

        cc = shutil.which("cc") or shutil.which("claude")
        if not cc:
            QMessageBox.warning(self, "Brak cc",
                                "Nie znaleziono 'cc' ani 'claude' w PATH.")
            return

        context = _build_project_context(Path(project_path), exclude=filename)
        prompt = _DPS_GEN_PROMPT.get(filename, _DPS_GEN_PROMPT["CLAUDE.md"]).format(
            context=context
        )

        setattr(self, f"_gen_buffer_{safe}", "")
        gen_output.clear()
        btn_run.setEnabled(False)
        btn_stop.setEnabled(True)
        btn_save.setEnabled(False)
        status.setText("Generowanie…")

        proc = QProcess(self)
        proc.readyReadStandardOutput.connect(lambda: self._gen_on_stdout(filename))
        proc.readyReadStandardError.connect(lambda: self._gen_on_stderr(filename))
        proc.finished.connect(lambda code, _: self._gen_on_finished(filename, code))
        setattr(self, f"_gen_process_{safe}", proc)
        if not _start_cc_with_prompt(proc, cc, prompt):
            status.setText("Błąd startu procesu")
            btn_run.setEnabled(True)
            btn_stop.setEnabled(False)

    def _gen_on_stdout(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        proc: QProcess | None = getattr(self, f"_gen_process_{safe}", None)
        if not proc:
            return
        gen_output: QPlainTextEdit = getattr(self, f"_gen_output_{safe}")
        raw = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunk = ""
                if obj.get("type") == "content_block_delta":
                    chunk = obj.get("delta", {}).get("text", "")
                elif obj.get("type") == "text":
                    chunk = obj.get("text", "")
                elif obj.get("type") == "result":
                    chunk = obj.get("result", "")
                if chunk:
                    buf = getattr(self, f"_gen_buffer_{safe}", "") + chunk
                    setattr(self, f"_gen_buffer_{safe}", buf)
                    gen_output.moveCursor(QTextCursor.MoveOperation.End)
                    gen_output.insertPlainText(chunk)
            except (json.JSONDecodeError, KeyError):
                buf = getattr(self, f"_gen_buffer_{safe}", "") + line + "\n"
                setattr(self, f"_gen_buffer_{safe}", buf)
                gen_output.moveCursor(QTextCursor.MoveOperation.End)
                gen_output.insertPlainText(line + "\n")

    def _gen_on_stderr(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        proc: QProcess | None = getattr(self, f"_gen_process_{safe}", None)
        if not proc:
            return
        gen_output: QPlainTextEdit = getattr(self, f"_gen_output_{safe}")
        raw = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        if raw.strip():
            gen_output.moveCursor(QTextCursor.MoveOperation.End)
            gen_output.insertPlainText(f"\n[STDERR] {raw}")

    def _gen_on_finished(self, filename: str, exit_code: int) -> None:
        safe = filename.replace(".", "_")
        btn_run: QPushButton = getattr(self, f"_gen_btn_run_{safe}")
        btn_stop: QPushButton = getattr(self, f"_gen_btn_stop_{safe}")
        btn_save: QPushButton = getattr(self, f"_gen_btn_save_{safe}")
        status: QLabel = getattr(self, f"_gen_status_{safe}")
        has = bool(getattr(self, f"_gen_buffer_{safe}", "").strip())
        btn_run.setEnabled(True)
        btn_stop.setEnabled(False)
        btn_save.setEnabled(has)
        status.setText("Gotowe — sprawdź i kliknij Zapisz" if has else f"Błąd (kod {exit_code})")

    def _gen_stop(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        proc: QProcess | None = getattr(self, f"_gen_process_{safe}", None)
        status: QLabel = getattr(self, f"_gen_status_{safe}")
        btn_run: QPushButton = getattr(self, f"_gen_btn_run_{safe}")
        btn_stop: QPushButton = getattr(self, f"_gen_btn_stop_{safe}")
        if proc and proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()
            status.setText("Przerwano")
        btn_run.setEnabled(True)
        btn_stop.setEnabled(False)

    def _gen_save(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        status: QLabel = getattr(self, f"_gen_status_{safe}")
        btn_save: QPushButton = getattr(self, f"_gen_btn_save_{safe}")
        badge: QLabel = getattr(self, f"_gen_badge_{safe}")
        content = getattr(self, f"_gen_buffer_{safe}", "").strip()
        if not content:
            return
        project_path = self._path_edit.toPlainText().strip()
        if not project_path:
            return
        target = Path(project_path) / filename
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return
        status.setText(f"Zapisano {filename}")
        badge.setText("Wygenerowano")
        badge.setStyleSheet(
            "background:#1a2a3a;color:#61afef;border-radius:3px;"
            "padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        badge.setVisible(True)
        btn_save.setEnabled(False)
        # Przełącz stack na konwerter i odśwież
        action_stack: QStackedWidget | None = getattr(
            self, f"_md_action_stack_{safe}", None
        )
        if action_stack:
            action_stack.setCurrentIndex(0)
        self._reload_md_file(filename)

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

        # Przełącz stack między konwerterem a generatorem
        action_stack: QStackedWidget | None = getattr(
            self, f"_md_action_stack_{safe}", None
        )
        if not file_path.exists():
            if action_stack:
                action_stack.setCurrentIndex(1)  # generator
            if sections_layout:
                self._clear_sections_layout(sections_layout)
                lbl = QLabel(
                    f"Plik {filename} nie istnieje — użyj panelu poniżej aby go wygenerować.",
                    styleSheet=_LBL_WARN,
                )
                lbl.setWordWrap(True)
                sections_layout.insertWidget(sections_layout.count() - 1, lbl)
            return
        if action_stack:
            action_stack.setCurrentIndex(0)  # konwerter

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

    # ---- Konwersja MD → DPS (generyczna dla CLAUDE / ARCHITECTURE / CONVENTIONS) #

    _CONV_PROMPTS: dict[str, str] = _DPS_CONV_PROMPT

    # Stan konwersji — słowniki per filename (safe key)
    _conv_processes: dict[str, QProcess] = {}
    _conv_buffers: dict[str, str] = {}

    def _build_md_converter(self, filename: str) -> QWidget:
        """Panel konwersji danego pliku MD do formatu DPS."""
        safe = filename.replace(".", "_")
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background:#12141a;border:1px solid #3c3c3c;border-radius:4px;}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        # Nagłówek
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Konwersja do formatu DPS", styleSheet=_LBL_HEAD))
        hdr.addStretch()
        badge = QLabel("")
        badge.setVisible(False)
        hdr.addWidget(badge)
        lay.addLayout(hdr)

        desc = QLabel(
            f"Konwertuje {filename} do formatu zgodnego z modułem Projektant — "
            f"każda sekcja zostanie opakowana w znaczniki <!-- SECTION:nazwa -->.\n"
            f"Oryginał zostanie zachowany w _no_dps/<nazwa>__<projekt>.md."
        )
        desc.setStyleSheet("color:#6b7280;font-size:10px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addWidget(_sep())

        # Podgląd
        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setFont(_FONT_MONO)
        output.setFixedHeight(80)
        output.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#98c379;"
            "border:1px solid #2a3a2a;border-radius:3px;padding:4px;}"
        )
        output.setPlaceholderText(f"Tutaj pojawi się skonwertowana treść {filename}…")
        lay.addWidget(output)

        # Przyciski
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_run = QPushButton("✦  Konwertuj przez AI")
        btn_run.setStyleSheet(
            "QPushButton{background:#2a1a3a;color:#c678dd;"
            "border:1px solid #4a2a5a;border-radius:3px;padding:5px 14px;font-weight:bold}"
            "QPushButton:hover{background:#4a2a5a}"
            "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
        )
        btn_row.addWidget(btn_run)

        btn_stop = QPushButton("■  Stop")
        btn_stop.setStyleSheet(
            "QPushButton{background:#3a2a00;color:#e5c07b;"
            "border:1px solid #5a4000;border-radius:3px;padding:5px 12px}"
            "QPushButton:hover{background:#5a4000}"
        )
        btn_stop.setEnabled(False)
        btn_row.addWidget(btn_stop)

        btn_apply = QPushButton(f"→ Zapisz jako {filename}")
        btn_apply.setStyleSheet(_BTN_GREEN)
        btn_apply.setEnabled(False)
        btn_row.addWidget(btn_apply)

        btn_row.addStretch()
        status_lbl = QLabel("", styleSheet=_LBL_DIM)
        status_lbl.setFont(_FONT_SMALL)
        btn_row.addWidget(status_lbl)
        lay.addLayout(btn_row)

        # Zapisz referencje potrzebne w callbackach
        setattr(self, f"_conv_output_{safe}", output)
        setattr(self, f"_conv_btn_run_{safe}", btn_run)
        setattr(self, f"_conv_btn_stop_{safe}", btn_stop)
        setattr(self, f"_conv_btn_apply_{safe}", btn_apply)
        setattr(self, f"_conv_status_{safe}", status_lbl)
        setattr(self, f"_conv_badge_{safe}", badge)

        btn_run.clicked.connect(lambda: self._conv_run(filename))
        btn_stop.clicked.connect(lambda: self._conv_stop(filename))
        btn_apply.clicked.connect(lambda: self._conv_apply(filename))

        return frame

    def _conv_run(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        output: QPlainTextEdit = getattr(self, f"_conv_output_{safe}")
        btn_run: QPushButton = getattr(self, f"_conv_btn_run_{safe}")
        btn_stop: QPushButton = getattr(self, f"_conv_btn_stop_{safe}")
        btn_apply: QPushButton = getattr(self, f"_conv_btn_apply_{safe}")
        status_lbl: QLabel = getattr(self, f"_conv_status_{safe}")
        badge: QLabel = getattr(self, f"_conv_badge_{safe}")

        project_path = self._path_edit.toPlainText().strip()
        if not project_path:
            status_lbl.setText("Brak ścieżki projektu")
            return

        md_path = Path(project_path) / filename
        if not md_path.exists():
            status_lbl.setText(f"Brak pliku {filename} w projekcie")
            return

        cc = shutil.which("cc") or shutil.which("claude")
        if not cc:
            QMessageBox.warning(
                self, "Brak cc",
                "Nie znaleziono polecenia 'cc' ani 'claude' w PATH.\n"
                "Zainstaluj Claude Code CLI lub dodaj go do PATH.",
            )
            return

        content = md_path.read_text(encoding="utf-8")
        if "<!-- SECTION:" in content:
            reply = QMessageBox.question(
                self, "Już DPS?",
                f"Plik {filename} wygląda na już skonwertowany (zawiera znaczniki SECTION).\n"
                "Konwertować ponownie?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        prompt_template = self._CONV_PROMPTS.get(filename, self._CONV_PROMPTS["CLAUDE.md"])
        prompt = prompt_template.format(content=content)

        self._conv_buffers[safe] = ""
        output.clear()
        btn_run.setEnabled(False)
        btn_stop.setEnabled(True)
        btn_apply.setEnabled(False)
        status_lbl.setText("Konwertowanie…")
        badge.setVisible(False)

        proc = QProcess(self)
        proc.readyReadStandardOutput.connect(lambda: self._conv_on_stdout(filename))
        proc.readyReadStandardError.connect(lambda: self._conv_on_stderr(filename))
        proc.finished.connect(lambda code, _: self._conv_on_finished(filename, code))
        self._conv_processes[safe] = proc
        if not _start_cc_with_prompt(proc, cc, prompt):
            status_lbl.setText("Błąd startu procesu")
            btn_run.setEnabled(True)
            btn_stop.setEnabled(False)

    def _conv_on_stdout(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        proc = self._conv_processes.get(safe)
        if not proc:
            return
        output: QPlainTextEdit = getattr(self, f"_conv_output_{safe}")
        raw = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunk = ""
                if obj.get("type") == "content_block_delta":
                    chunk = obj.get("delta", {}).get("text", "")
                elif obj.get("type") == "text":
                    chunk = obj.get("text", "")
                elif obj.get("type") == "result":
                    chunk = obj.get("result", "")
                if chunk:
                    self._conv_buffers[safe] = self._conv_buffers.get(safe, "") + chunk
                    output.moveCursor(QTextCursor.MoveOperation.End)
                    output.insertPlainText(chunk)
            except (json.JSONDecodeError, KeyError):
                self._conv_buffers[safe] = self._conv_buffers.get(safe, "") + line + "\n"
                output.moveCursor(QTextCursor.MoveOperation.End)
                output.insertPlainText(line + "\n")

    def _conv_on_stderr(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        proc = self._conv_processes.get(safe)
        if not proc:
            return
        output: QPlainTextEdit = getattr(self, f"_conv_output_{safe}")
        raw = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace")
        if raw.strip():
            output.moveCursor(QTextCursor.MoveOperation.End)
            output.insertPlainText(f"\n[STDERR] {raw}")

    def _conv_on_finished(self, filename: str, exit_code: int) -> None:
        safe = filename.replace(".", "_")
        btn_run: QPushButton = getattr(self, f"_conv_btn_run_{safe}")
        btn_stop: QPushButton = getattr(self, f"_conv_btn_stop_{safe}")
        btn_apply: QPushButton = getattr(self, f"_conv_btn_apply_{safe}")
        status_lbl: QLabel = getattr(self, f"_conv_status_{safe}")
        has_output = bool(self._conv_buffers.get(safe, "").strip())
        btn_run.setEnabled(True)
        btn_stop.setEnabled(False)
        btn_apply.setEnabled(has_output)
        if exit_code == 0 and has_output:
            status_lbl.setText("Gotowe — sprawdź podgląd i kliknij Zapisz")
        else:
            status_lbl.setText(
                f"Zakończono (kod {exit_code})" if exit_code != 0 else "Brak wyjścia AI"
            )

    def _conv_stop(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        proc = self._conv_processes.get(safe)
        status_lbl: QLabel = getattr(self, f"_conv_status_{safe}")
        btn_run: QPushButton = getattr(self, f"_conv_btn_run_{safe}")
        btn_stop: QPushButton = getattr(self, f"_conv_btn_stop_{safe}")
        if proc and proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()
            status_lbl.setText("Przerwano")
        btn_run.setEnabled(True)
        btn_stop.setEnabled(False)

    def _conv_apply(self, filename: str) -> None:
        safe = filename.replace(".", "_")
        status_lbl: QLabel = getattr(self, f"_conv_status_{safe}")
        btn_apply: QPushButton = getattr(self, f"_conv_btn_apply_{safe}")
        badge: QLabel = getattr(self, f"_conv_badge_{safe}")

        project_path = self._path_edit.toPlainText().strip()
        if not project_path:
            return
        new_content = self._conv_buffers.get(safe, "").strip()
        if not new_content:
            return

        md_path = Path(project_path) / filename

        try:
            backup_path = _backup_original(md_path) if md_path.exists() else None
            md_path.write_text(new_content, encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return

        backup_info = f"_no_dps/{backup_path.name}" if backup_path else "brak oryginału"
        status_lbl.setText(f"Zapisano · oryginał → {backup_info}")
        badge.setText("DPS")
        badge.setStyleSheet(
            "background:#1a3a1a;color:#98c379;border-radius:3px;"
            "padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        badge.setVisible(True)
        btn_apply.setEnabled(False)
        self._reload_md_file(filename)

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

    # ---- Logi Python -------------------------------------------------- #

    _RUN_LOG_PATH = Path.home() / ".claude" / "run_log.json"

    def _build_logi(self) -> QWidget:
        """Zakładka Logi — wywołania skryptów Pythona z run_log.json."""
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Nagłówek z licznikiem i przyciskiem odśwież
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Uruchomienia skryptów Pythona (CC)", styleSheet=_LBL_HEAD))
        hdr.addStretch()
        self._logi_count_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._logi_count_lbl.setFont(_FONT_SMALL)
        hdr.addWidget(self._logi_count_lbl)
        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedWidth(28)
        btn_refresh.setStyleSheet(_BTN)
        btn_refresh.clicked.connect(self.reload_logi)
        hdr.addWidget(btn_refresh)
        root.addLayout(hdr)

        # Pole tekstowe z wpisami
        self._logi_view = QPlainTextEdit()
        self._logi_view.setReadOnly(True)
        self._logi_view.setFont(_FONT_MONO)
        self._logi_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#cccccc;"
            "border:1px solid #3c3c3c;border-radius:3px;padding:6px}"
        )
        self._logi_view.setPlaceholderText(
            "(brak wpisów — skrypty Python uruchamiane przez CC pojawią się tutaj)"
        )
        root.addWidget(self._logi_view, stretch=1)

        # Statystyki na dole
        stats_frame = QFrame()
        stats_frame.setStyleSheet(_CARD)
        sl = QHBoxLayout(stats_frame)
        sl.setContentsMargins(8, 4, 8, 4)
        self._logi_total_lbl = _val("Łącznie: —")
        self._logi_last_lbl = _val("Ostatnie: —", _LBL_DIM)
        self._logi_session_lbl = _val("Projekt: —", _LBL_DIM)
        sl.addWidget(self._logi_total_lbl)
        sl.addWidget(QLabel(" | ", styleSheet=_LBL_DIM))
        sl.addWidget(self._logi_last_lbl)
        sl.addWidget(QLabel(" | ", styleSheet=_LBL_DIM))
        sl.addWidget(self._logi_session_lbl)
        sl.addStretch()
        root.addWidget(stats_frame)

        # Watcher na run_log.json
        self._logi_watcher = QFileSystemWatcher(w)
        if self._RUN_LOG_PATH.exists():
            self._logi_watcher.addPath(str(self._RUN_LOG_PATH))
        self._logi_watcher.fileChanged.connect(self._on_logi_changed)

        # Polling gdy plik jeszcze nie istnieje
        self._logi_poll = QTimer(w)
        self._logi_poll.setInterval(10_000)
        self._logi_poll.timeout.connect(self._logi_poll_tick)
        if not self._RUN_LOG_PATH.exists():
            self._logi_poll.start()

        return w

    def _logi_poll_tick(self) -> None:
        if self._RUN_LOG_PATH.exists():
            self._logi_watcher.addPath(str(self._RUN_LOG_PATH))
            self._logi_poll.stop()
            self.reload_logi()

    def _on_logi_changed(self, path: str) -> None:
        # Re-podepnij po nadpisaniu pliku (QFileSystemWatcher traci ścieżkę)
        if path not in self._logi_watcher.files():
            if Path(path).exists():
                self._logi_watcher.addPath(path)
        self.reload_logi()

    def reload_logi(self) -> None:
        """Wczytaj run_log.json i wyświetl wpisy pasujące do cwd tego slotu."""
        project_path = self._path_edit.toPlainText().strip()

        if not self._RUN_LOG_PATH.exists():
            self._logi_view.setPlainText("(plik run_log.json jeszcze nie istnieje)")
            self._logi_count_lbl.setText("")
            self._logi_total_lbl.setText("Łącznie: 0")
            self._logi_last_lbl.setText("Ostatnie: —")
            self._logi_session_lbl.setText("Projekt: —")
            return

        try:
            all_entries = json.loads(self._RUN_LOG_PATH.read_text(encoding="utf-8"))
            if not isinstance(all_entries, list):
                all_entries = []
        except Exception:
            all_entries = []

        # Filtruj po cwd jeśli ścieżka projektu jest ustawiona
        if project_path:
            norm_proj = Path(project_path).resolve()
            def _matches(e: dict) -> bool:
                cwd = e.get("cwd", "")
                if not cwd:
                    return False
                try:
                    return Path(cwd).resolve() == norm_proj
                except Exception:
                    return False
            entries = [e for e in all_entries if _matches(e)]
        else:
            entries = list(all_entries)

        total_all = len(all_entries)
        total_proj = len(entries)

        # Nagłówek licznika
        if project_path:
            proj_name = Path(project_path).name
            self._logi_count_lbl.setText(
                f"{total_proj} dla projektu  ·  {total_all} łącznie"
            )
            self._logi_session_lbl.setText(f"Projekt: {proj_name}")
        else:
            self._logi_count_lbl.setText(f"{total_all} łącznie")
            self._logi_session_lbl.setText("Projekt: (wszystkie)")

        self._logi_total_lbl.setText(f"Łącznie wywołań: {total_proj}")

        if entries:
            last = entries[-1]
            self._logi_last_lbl.setText(f"Ostatnie: {last.get('ts', '—')}")
        else:
            self._logi_last_lbl.setText("Ostatnie: —")

        # Renderuj wpisy — od najnowszego
        lines = []
        for e in reversed(entries):
            ts = e.get("ts", "")
            cmd = e.get("cmd", "").strip()
            cwd = e.get("cwd", "")
            short_cwd = Path(cwd).name if cwd else ""
            lines.append(f"{ts}  [{short_cwd}]\n  > {cmd}\n")

        self._logi_view.setPlainText("\n".join(lines) if lines else "(brak wywołań dla tego projektu)")
        # Przewiń na górę (najnowsze)
        self._logi_view.moveCursor(QTextCursor.MoveOperation.Start)

    # ---- Historia ------------------------------------------------------ #


    def _build_historia(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(QLabel("Historia sesji:", styleSheet=_LBL_HEAD))
        top.addStretch()
        self._btn_hist_refresh = QPushButton("⟳")
        self._btn_hist_refresh.setFixedWidth(28)
        self._btn_hist_refresh.setStyleSheet(_BTN)
        top.addWidget(self._btn_hist_refresh)
        lay.addLayout(top)

        self._transcript = QPlainTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setFont(_FONT_MONO)
        self._transcript.setStyleSheet(
            "QPlainTextEdit{background:#141414;color:#cccccc;border:none;padding:4px;}"
        )
        self._transcript.setPlaceholderText("(brak wpisów transkryptu)")
        lay.addWidget(self._transcript, stretch=1)

        self._last_msg = self._transcript
        return w

    # ---- Sesje --------------------------------------------------------- #

    def _build_sesje(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Pasek narzędzi
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        self._lbl_sesje_path = QLabel("", styleSheet=_LBL_DIM)
        self._lbl_sesje_path.setFont(_FONT_MONO)
        toolbar.addWidget(self._lbl_sesje_path, stretch=1)
        self._btn_sesje_refresh = QPushButton("⟳  Odśwież")
        self._btn_sesje_refresh.setStyleSheet(_BTN)
        self._btn_sesje_refresh.setFixedWidth(90)
        toolbar.addWidget(self._btn_sesje_refresh)
        lay.addLayout(toolbar)

        # Widok konwersacji
        self._sesje_view = QTextEdit()
        self._sesje_view.setReadOnly(True)
        self._sesje_view.setFont(_FONT_MONO)
        self._sesje_view.setStyleSheet(
            "QTextEdit{"
            "background:#0d0d0d;color:#cccccc;"
            "border:none;padding:8px;"
            "}"
        )
        lay.addWidget(self._sesje_view, stretch=1)

        # Stopka ze statystykami
        footer = QFrame()
        footer.setStyleSheet("QFrame{background:#1a1a1a;border-top:1px solid #2a2a2a;}")
        footer_lay = QHBoxLayout(footer)
        footer_lay.setContentsMargins(8, 3, 8, 3)
        self._lbl_cc_sessions = QLabel("", styleSheet=_LBL_DIM)
        self._lbl_cc_last = QLabel("", styleSheet=_LBL_DIM)
        footer_lay.addWidget(self._lbl_cc_sessions)
        footer_lay.addWidget(QLabel("·", styleSheet=_LBL_DIM))
        footer_lay.addWidget(self._lbl_cc_last)
        footer_lay.addStretch()
        lay.addWidget(footer)

        return w

    def _reload_sesje_view(self) -> None:
        """Wczytuje i renderuje konwersację z najnowszego transkryptu projektu."""
        project_path = self._path_edit.toPlainText().strip()
        if not project_path:
            self._sesje_view.setHtml(
                "<p style='color:#5c6370;margin:16px;'>Brak ścieżki projektu.</p>"
            )
            self._lbl_sesje_path.setText("")
            return

        transcript_path = find_latest_transcript(project_path)
        if transcript_path is None:
            self._sesje_view.setHtml(
                "<p style='color:#5c6370;margin:16px;'>"
                "Brak transkryptów w ~/.claude/projects/ dla tego projektu.</p>"
            )
            self._lbl_sesje_path.setText("(brak transkryptów)")
            return

        self._lbl_sesje_path.setText(str(transcript_path))
        messages = read_transcript_messages(transcript_path)

        if not messages:
            self._sesje_view.setHtml(
                "<p style='color:#5c6370;margin:16px;'>Brak wiadomości w transkrypcie.</p>"
            )
            return

        self._sesje_view.setHtml(_render_conversation_html(messages))

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

    # ---- Full Converter ------------------------------------------------ #

    def _build_full_converter(self) -> QWidget:
        self._full_converter = _FullConverterPanel()
        return self._full_converter

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

    _TAB_ZADANIOWIEC = 3  # indeks zakładki ZADANIOWIEC w self._tabs

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
        self._btn_sesje_refresh.clicked.connect(self._reload_sesje_view)
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
        if index == self._TAB_ZADANIOWIEC and not self._zadaniowiec_loaded:
            self._zadaniowiec_loaded = True
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
            self.reload_logi()

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
            self._zadaniowiec_loaded = False
            self._path_edit.setPlainText(folder)
            self.reload_plan()
            self.reload_pcc()
            self.reload_stats()
            self.reload_history()
            self.reload_md_files()
            if self._tabs.currentIndex() == self._TAB_ZADANIOWIEC:
                self._zadaniowiec_loaded = True
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
        count_txt = f"{h.transcript_count} sesji CC" if h.transcript_count else "0 sesji CC"
        self._lbl_cc_sessions.setText(count_txt)
        if h.transcript_last_at:
            self._lbl_cc_last.setText(
                "ostatnia: " + h.transcript_last_at.strftime("%Y-%m-%d %H:%M")
            )
        else:
            self._lbl_cc_last.setText("")
        self._reload_sesje_view()


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

    def _show_git_init_dialog(self, path: str, then_round_end: bool = False) -> None:
        dlg = GitInitDialog(path, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._btn_push.setEnabled(False)
        self._btn_round.setEnabled(False)
        self._git_init_then_round_end = then_round_end
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
        if not Path(path).is_dir():
            QMessageBox.warning(self, "Zakoncz runde", f"Katalog projektu nie istnieje:\n{path}")
            return
        if not (Path(path) / ".git").exists():
            reply = QMessageBox.question(
                self,
                "Brak repozytorium Git",
                "Projekt nie ma repozytorium git.\n\n"
                "Chcesz najpierw zainicjalizować repozytorium, a następnie zakończyć rundę?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._show_git_init_dialog(path, then_round_end=True)
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
            if self._git_init_then_round_end:
                self._git_init_then_round_end = False
                path = self._path_edit.toPlainText().strip()
                if path:
                    self._btn_round.setEnabled(False)
                    self._workflow.run_round_end(path)
                return
        if name == "git_init":
            self._git_init_then_round_end = False

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
            full_msg = msg or "Blad operacji"
            if name == "round_end":
                full_msg = "PLAN.md zostal wyczyszczony, ale push nie powiodl sie:\n\n" + full_msg
            QMessageBox.critical(self, title, full_msg)

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


# ── Full Converter ────────────────────────────────────────────────────────────

class _FullConverterPanel(QWidget):
    """Panel pełnej konwersji projektu do formatu DPS.

    Przepływ:
      1. Wybór folderu projektu
      2. Analiza — wykrycie plików .md i ocena stopnia zgodności z DPS
      3. Rename — zmiana nazw plików do kanonicznych nazw DPS
      4. Konwersja — sekwencyjna konwersja każdego pliku przez cc CLI
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._queue: list[str] = []       # pliki do przetworzenia (generowanie + konwersja)
        self._gen_queue: list[str] = []   # pliki do wygenerowania od zera
        self._current_file: str = ""
        self._current_mode: str = ""      # "generate" | "convert"
        self._conv_process: QProcess | None = None
        self._conv_buffer: str = ""
        self._missing_files: list[str] = []
        self._setup_ui()

    # ------------------------------------------------------------------ #
    # UI                                                                   #
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Nagłówek
        hdr = QHBoxLayout()
        title = QLabel("Full Converter — konwersja projektu do formatu DPS")
        title.setStyleSheet("color:#cccccc;font-size:13px;font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._global_badge = QLabel("")
        self._global_badge.setVisible(False)
        hdr.addWidget(self._global_badge)
        root.addLayout(hdr)

        desc = QLabel(
            "Analizuje wybrany folder projektu, zmienia nazwy plików .md do standardu DPS "
            "(CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md), generuje brakujące pliki przez AI "
            "i konwertuje każdy z nich do formatu z oznaczonymi sekcjami <!-- SECTION:x -->.\n"
            "Oryginały są zachowywane w podfolderze _no_dps/ jako <nazwa>__<projekt>.md."
        )
        desc.setStyleSheet("color:#6b7280;font-size:10px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        root.addWidget(_sep())

        # Wybór folderu
        folder_row = QHBoxLayout()
        self._path_lbl = QLabel("(nie wybrano folderu)")
        self._path_lbl.setFont(_FONT_MONO)
        self._path_lbl.setStyleSheet(_LBL_DIM)
        self._path_lbl.setWordWrap(True)
        folder_row.addWidget(self._path_lbl, stretch=1)
        btn_pick = QPushButton("Wybierz folder…")
        btn_pick.setStyleSheet(_BTN)
        btn_pick.clicked.connect(self._on_pick_folder)
        folder_row.addWidget(btn_pick)
        btn_analyze = QPushButton("Analizuj")
        btn_analyze.setStyleSheet(_BTN_ACCENT)
        btn_analyze.clicked.connect(self._on_analyze)
        self._btn_analyze = btn_analyze
        folder_row.addWidget(btn_analyze)
        root.addLayout(folder_row)

        # Splitter: analiza (góra) | log konwersji (dół)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Panel analizy
        analysis_frame = QFrame()
        analysis_frame.setStyleSheet(_CARD)
        af_lay = QVBoxLayout(analysis_frame)
        af_lay.setContentsMargins(8, 6, 8, 8)
        af_lay.setSpacing(4)
        af_lay.addWidget(QLabel("Analiza dokumentacji projektu", styleSheet=_LBL_HEAD))

        self._analysis_view = QPlainTextEdit()
        self._analysis_view.setReadOnly(True)
        self._analysis_view.setFont(_FONT_MONO)
        self._analysis_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#cccccc;"
            "border:1px solid #3c3c3c;border-radius:3px;padding:6px;}"
        )
        self._analysis_view.setPlaceholderText(
            "Kliknij 'Analizuj' aby zobaczyć stan dokumentacji projektu…"
        )
        af_lay.addWidget(self._analysis_view)

        # Pasek akcji rename + generuj
        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        self._btn_rename = QPushButton("1. Zmień nazwy do DPS")
        self._btn_rename.setStyleSheet(
            "QPushButton{background:#2a2a1a;color:#e5c07b;"
            "border:1px solid #5a5a20;border-radius:3px;padding:5px 12px;font-weight:bold}"
            "QPushButton:hover{background:#4a4a20}"
            "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
        )
        self._btn_rename.setEnabled(False)
        self._btn_rename.clicked.connect(self._on_rename)
        actions_row.addWidget(self._btn_rename)

        self._btn_generate = QPushButton("1b. Generuj brakujące przez AI")
        self._btn_generate.setStyleSheet(
            "QPushButton{background:#1a2a3a;color:#61afef;"
            "border:1px solid #2a4a6a;border-radius:3px;padding:5px 12px;font-weight:bold}"
            "QPushButton:hover{background:#2a4a6a}"
            "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
        )
        self._btn_generate.setEnabled(False)
        self._btn_generate.clicked.connect(self._on_generate_missing)
        actions_row.addWidget(self._btn_generate)

        actions_row.addStretch()
        self._rename_status = QLabel("", styleSheet=_LBL_DIM)
        actions_row.addWidget(self._rename_status)
        af_lay.addLayout(actions_row)

        splitter.addWidget(analysis_frame)

        # Panel logu konwersji
        log_frame = QFrame()
        log_frame.setStyleSheet(_CARD)
        lf_lay = QVBoxLayout(log_frame)
        lf_lay.setContentsMargins(8, 6, 8, 8)
        lf_lay.setSpacing(4)

        log_hdr = QHBoxLayout()
        log_hdr.addWidget(QLabel("Log operacji AI", styleSheet=_LBL_HEAD))
        log_hdr.addStretch()
        self._progress_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._progress_lbl.setFont(_FONT_SMALL)
        log_hdr.addWidget(self._progress_lbl)
        lf_lay.addLayout(log_hdr)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(_FONT_MONO)
        self._log_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#98c379;"
            "border:1px solid #2a3a2a;border-radius:3px;padding:6px;}"
        )
        self._log_view.setPlaceholderText("Tu pojawi się streaming odpowiedzi AI…")
        lf_lay.addWidget(self._log_view)

        # Przyciski konwersji
        conv_row = QHBoxLayout()
        self._btn_convert = QPushButton("2. Konwertuj wszystkie pliki przez AI")
        self._btn_convert.setStyleSheet(
            "QPushButton{background:#2a1a3a;color:#c678dd;"
            "border:1px solid #4a2a5a;border-radius:3px;padding:5px 14px;font-weight:bold}"
            "QPushButton:hover{background:#4a2a5a}"
            "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
        )
        self._btn_convert.setEnabled(False)
        self._btn_convert.clicked.connect(self._on_convert_all)
        conv_row.addWidget(self._btn_convert)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setStyleSheet(
            "QPushButton{background:#3a2a00;color:#e5c07b;"
            "border:1px solid #5a4000;border-radius:3px;padding:5px 12px}"
            "QPushButton:hover{background:#5a4000}"
        )
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        conv_row.addWidget(self._btn_stop)

        conv_row.addStretch()
        self._conv_status = QLabel("", styleSheet=_LBL_DIM)
        self._conv_status.setFont(_FONT_SMALL)
        conv_row.addWidget(self._conv_status)
        lf_lay.addLayout(conv_row)

        splitter.addWidget(log_frame)
        splitter.setSizes([280, 340])
        root.addWidget(splitter, stretch=1)

    # ------------------------------------------------------------------ #
    # Logika                                                               #
    # ------------------------------------------------------------------ #

    def _on_pick_folder(self) -> None:
        start = str(self._project_path) if self._project_path else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder projektu", start)
        if not folder:
            return
        self._project_path = Path(folder)
        self._path_lbl.setText(folder)
        self._path_lbl.setStyleSheet(_LBL_VAL)
        self._btn_analyze.setEnabled(True)
        self._btn_rename.setEnabled(False)
        self._btn_generate.setEnabled(False)
        self._btn_convert.setEnabled(False)
        self._analysis_view.clear()
        self._log_view.clear()
        self._global_badge.setVisible(False)
        self._rename_status.setText("")
        self._conv_status.setText("")
        self._progress_lbl.setText("")
        self._missing_files = []

    def _on_analyze(self) -> None:
        if not self._project_path:
            return
        lines, rename_needed, convert_ready, missing = _analyze_project(self._project_path)
        self._missing_files = missing
        self._analysis_view.setPlainText("\n".join(lines))
        self._btn_rename.setEnabled(rename_needed)
        self._btn_generate.setEnabled(bool(missing) and not rename_needed)
        self._btn_convert.setEnabled(convert_ready and not rename_needed)

    def _on_rename(self) -> None:
        if not self._project_path:
            return
        renamed, errors = _rename_to_dps(self._project_path)
        msgs = []
        for old, new in renamed:
            msgs.append(f"  ✓  {old}  →  {new}")
        for err in errors:
            msgs.append(f"  ✗  {err}")
        if msgs:
            existing = self._analysis_view.toPlainText()
            self._analysis_view.setPlainText(
                existing + "\n\n── Rename ──\n" + "\n".join(msgs)
            )
        self._rename_status.setText(f"Zmieniono {len(renamed)} plików")
        self._btn_rename.setEnabled(False)
        self._btn_generate.setEnabled(bool(self._missing_files))
        self._btn_convert.setEnabled(True)

    def _on_generate_missing(self) -> None:
        if not self._project_path or not self._missing_files:
            return
        cc = shutil.which("cc") or shutil.which("claude")
        if not cc:
            QMessageBox.warning(self, "Brak cc",
                                "Nie znaleziono polecenia 'cc' ani 'claude' w PATH.")
            return
        self._gen_queue = list(self._missing_files)
        self._queue = []
        self._log_view.clear()
        self._btn_generate.setEnabled(False)
        self._btn_rename.setEnabled(False)
        self._btn_convert.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._global_badge.setVisible(False)
        self._log("── Generowanie brakujących plików ──")
        self._run_next_gen()

    def _on_convert_all(self) -> None:
        if not self._project_path:
            return
        cc = shutil.which("cc") or shutil.which("claude")
        if not cc:
            QMessageBox.warning(self, "Brak cc",
                                "Nie znaleziono polecenia 'cc' ani 'claude' w PATH.")
            return
        self._queue = []
        for fname in sorted(_DPS_CONVERTIBLE):
            p = self._project_path / fname
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
                if "<!-- SECTION:" not in content:
                    self._queue.append(fname)
        if not self._queue:
            self._conv_status.setText("Brak plików do konwersji (wszystkie już DPS?)")
            return
        self._log_view.clear()
        self._btn_convert.setEnabled(False)
        self._btn_rename.setEnabled(False)
        self._btn_generate.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._global_badge.setVisible(False)
        self._log("── Rozpoczynam konwersję ──")
        self._current_mode = "convert"
        self._conv_next()

    # ---- Generowanie od zera ----------------------------------------- #

    def _run_next_gen(self) -> None:
        if not self._gen_queue:
            self._log("\n── Generowanie zakończone ──")
            self._btn_stop.setEnabled(False)
            self._btn_generate.setEnabled(False)
            self._btn_convert.setEnabled(True)
            self._progress_lbl.setText("")
            self._conv_status.setText("Wygenerowano — kliknij 'Konwertuj' aby dodać sekcje")
            return

        self._current_file = self._gen_queue.pop(0)
        done = len(self._missing_files) - len(self._gen_queue)
        self._progress_lbl.setText(
            f"Generuję {self._current_file}  ({done}/{len(self._missing_files)})"
        )
        self._conv_status.setText(f"Generuję {self._current_file}…")
        self._log(f"\n── Generuję {self._current_file} ──")

        context = _build_project_context(self._project_path, exclude=self._current_file)
        prompt = _DPS_GEN_PROMPT.get(
            self._current_file, _DPS_GEN_PROMPT["CLAUDE.md"]
        ).format(context=context)

        self._conv_buffer = ""
        self._current_mode = "generate"
        cc = shutil.which("cc") or shutil.which("claude")
        self._conv_process = QProcess(self)
        self._conv_process.readyReadStandardOutput.connect(self._on_stdout)
        self._conv_process.readyReadStandardError.connect(self._on_stderr)
        self._conv_process.finished.connect(self._on_file_finished)
        if not _start_cc_with_prompt(self._conv_process, cc, prompt):
            self._log(f"  [BŁĄD] start procesu dla {self._current_file}")
            self._run_next_gen()

    # ---- Wspólna kolejka konwersji ------------------------------------ #

    def _conv_next(self) -> None:
        if not self._queue:
            self._log("\n── Konwersja zakończona ──")
            self._btn_stop.setEnabled(False)
            self._btn_convert.setEnabled(False)
            self._progress_lbl.setText("")
            self._global_badge.setText("DPS ✓")
            self._global_badge.setStyleSheet(
                "background:#1a3a1a;color:#98c379;border-radius:3px;"
                "padding:2px 10px;font-size:10px;font-weight:bold;"
            )
            self._global_badge.setVisible(True)
            return

        self._current_file = self._queue.pop(0)
        done = len(list(_DPS_CONVERTIBLE)) - len(self._queue)
        self._progress_lbl.setText(f"{self._current_file}  ({done}/{len(_DPS_CONVERTIBLE)})")
        self._conv_status.setText(f"Konwertuję {self._current_file}…")
        self._log(f"\n── {self._current_file} ──")

        md_path = self._project_path / self._current_file
        content = md_path.read_text(encoding="utf-8", errors="replace")
        prompt = _DPS_CONV_PROMPT.get(
            self._current_file, _DPS_CONV_PROMPT["CLAUDE.md"]
        ).format(content=content)

        self._conv_buffer = ""
        self._current_mode = "convert"
        cc = shutil.which("cc") or shutil.which("claude")
        self._conv_process = QProcess(self)
        self._conv_process.readyReadStandardOutput.connect(self._on_stdout)
        self._conv_process.readyReadStandardError.connect(self._on_stderr)
        self._conv_process.finished.connect(self._on_file_finished)
        if not _start_cc_with_prompt(self._conv_process, cc, prompt):
            self._log(f"  [BŁĄD] start procesu dla {self._current_file}")
            self._conv_next()

    def _on_stdout(self) -> None:
        if not self._conv_process:
            return
        raw = bytes(self._conv_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunk = ""
                if obj.get("type") == "content_block_delta":
                    chunk = obj.get("delta", {}).get("text", "")
                elif obj.get("type") == "text":
                    chunk = obj.get("text", "")
                elif obj.get("type") == "result":
                    chunk = obj.get("result", "")
                if chunk:
                    self._conv_buffer += chunk
                    self._log_chunk(chunk)
            except (json.JSONDecodeError, KeyError):
                self._conv_buffer += line + "\n"
                self._log_chunk(line + "\n")

    def _on_stderr(self) -> None:
        if not self._conv_process:
            return
        raw = bytes(self._conv_process.readAllStandardError()).decode("utf-8", errors="replace")
        if raw.strip():
            self._log(f"  [STDERR] {raw.strip()}")

    def _on_file_finished(self, exit_code: int, _exit_status) -> None:
        new_content = self._conv_buffer.strip()
        if exit_code == 0 and new_content:
            if self._current_mode == "generate":
                # Nowy plik — zapisujemy bezpośrednio (brak oryginału do backupu)
                try:
                    (self._project_path / self._current_file).write_text(
                        new_content, encoding="utf-8"
                    )
                    self._log(f"  ✓ Wygenerowano {self._current_file}")
                except OSError as e:
                    self._log(f"  ✗ Zapis {self._current_file}: {e}")
            else:
                backup = self._save_converted(self._current_file, new_content)
                backup_info = f"_no_dps/{backup.name}" if backup else "brak oryginału"
                self._log(f"  ✓ Zapisano {self._current_file} (oryginał → {backup_info})")
        else:
            self._log(f"  ✗ {self._current_file} — błąd (kod {exit_code})")

        if self._current_mode == "generate":
            self._run_next_gen()
        else:
            self._conv_next()

    def _on_stop(self) -> None:
        if self._conv_process and self._conv_process.state() != QProcess.ProcessState.NotRunning:
            self._conv_process.kill()
        self._queue.clear()
        self._gen_queue.clear()
        self._btn_stop.setEnabled(False)
        self._btn_convert.setEnabled(True)
        self._btn_generate.setEnabled(bool(self._missing_files))
        self._conv_status.setText("Przerwano")
        self._progress_lbl.setText("")

    def _save_converted(self, filename: str, content: str) -> Path | None:
        """Zapisuje skonwertowany plik, oryginał przenosi do _no_dps/. Zwraca ścieżkę backupu."""
        md_path = self._project_path / filename
        backup_path = _backup_original(md_path) if md_path.exists() else None
        md_path.write_text(content, encoding="utf-8")
        return backup_path

    def _log(self, text: str) -> None:
        self._log_view.moveCursor(QTextCursor.MoveOperation.End)
        self._log_view.insertPlainText(text + "\n")

    def _log_chunk(self, chunk: str) -> None:
        self._log_view.moveCursor(QTextCursor.MoveOperation.End)
        self._log_view.insertPlainText(chunk)


# ── Funkcje pomocnicze analizy i rename ──────────────────────────────────────

def _analyze_project(project_path: Path) -> tuple[list[str], bool, bool, list[str]]:
    """Zwraca (linie raportu, czy_potrzebny_rename, czy_można_konwertować, brakujące_pliki)."""
    lines: list[str] = []
    lines.append(f"Projekt: {project_path}")
    lines.append(f"Data:    {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    md_files = sorted(project_path.glob("*.md")) + sorted(project_path.glob("*.MD"))
    if not md_files:
        lines.append("⚠  Brak plików .md w katalogu projektu.")
        return lines, False, False, []

    lines.append(f"Znalezione pliki .md ({len(md_files)}):")
    lines.append("")

    rename_needed = False
    convertible_found = False

    for f in md_files:
        canon = _DPS_CANON.get(f.name.lower())
        is_readonly = canon in _DPS_READONLY

        content = ""
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

        size_kb = len(content.encode()) / 1024
        status_parts = []

        # Zgodność nazwy
        if canon is None:
            status_parts.append("❓ Nieznana nazwa")
        elif f.name != canon:
            status_parts.append(f"⚠  Nazwa → {canon}")
            if not is_readonly:
                rename_needed = True
        else:
            status_parts.append("✓ Nazwa OK")

        # Zgodność formatu / tryb
        if is_readonly:
            status_parts.append("— pomijany (tylko odczyt)")
        else:
            is_dps = "<!-- SECTION:" in content
            section_count = content.count("<!-- SECTION:")
            has_headings = bool(re.search(r"^#{2,3}\s", content, re.MULTILINE))
            if is_dps:
                status_parts.append(f"✓ DPS ({section_count} sekcji)")
            elif has_headings:
                status_parts.append("○ Zwykły MD (wymaga konwersji)")
                if canon in _DPS_CONVERTIBLE:
                    convertible_found = True
            else:
                status_parts.append("○ Brak sekcji")

        lines.append(f"  {f.name:<30}  {size_kb:5.1f} KB   {' | '.join(status_parts)}")

    lines.append("")

    # Podsumowanie — brakujące pliki konwertowalnych (bez README/ROADMAP/PLAN)
    canon_names = set(_DPS_CONVERTIBLE)
    existing_names = {f.name for f in md_files} | {
        _DPS_CANON.get(f.name.lower(), "") for f in md_files
    }
    missing_list = sorted(canon_names - existing_names)
    if missing_list:
        lines.append(f"⚠  Brakuje plików: {', '.join(missing_list)}  (można wygenerować przez AI)")

    if rename_needed:
        lines.append("→ Krok 1: Zmień nazwy plików do standardu DPS")
    if missing_list:
        lines.append("→ Krok 1b: Wygeneruj brakujące pliki przez AI")
    if convertible_found:
        lines.append("→ Krok 2: Konwertuj pliki do formatu DPS przez AI")
    if not rename_needed and not convertible_found and not missing_list:
        lines.append("✓ Projekt jest już w pełni zgodny z formatem DPS")

    return lines, rename_needed, convertible_found, missing_list


def _rename_to_dps(project_path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Zmienia nazwy plików .md do kanonicznych nazw DPS.

    Zwraca (lista (stara, nowa), błędy).
    """
    renamed: list[tuple[str, str]] = []
    errors: list[str] = []
    md_files = list(project_path.glob("*.md")) + list(project_path.glob("*.MD"))
    for f in md_files:
        canon = _DPS_CANON.get(f.name.lower())
        if canon and f.name != canon and canon not in _DPS_READONLY:
            target = project_path / canon
            if target.exists():
                errors.append(f"{f.name} → {canon} (cel już istnieje, pominięto)")
                continue
            try:
                f.rename(target)
                renamed.append((f.name, canon))
            except OSError as e:
                errors.append(f"{f.name} → {canon}: {e}")
    return renamed, errors


def _start_cc_with_prompt(proc: "QProcess", cc: str, prompt: str) -> bool:
    """Uruchamia cc CLI z promptem przez stdin zamiast argumentu.

    Zwraca True jeśli proces wystartował. Używa stdin żeby ominąć limit
    długości argumentu wiersza poleceń Windows i poprawnie przekazać prompt.
    """
    proc.setProgram(cc)
    proc.setArguments(["--print", "--output-format", "stream-json"])
    proc.start()
    if not proc.waitForStarted(3000):
        return False
    proc.write(prompt.encode("utf-8"))
    proc.closeWriteChannel()
    return True


def _backup_original(md_path: Path) -> Path:
    """Kopiuje oryginał do _no_dps/<nazwa>__<projekt>.md przed nadpisaniem.

    Zwraca ścieżkę do pliku backupu.
    """
    project_name = md_path.parent.name
    stem = md_path.stem
    backup_dir = md_path.parent / "_no_dps"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"{stem}__{project_name}.md"
    shutil.copy2(str(md_path), str(backup_path))
    return backup_path


def _build_project_context(project_path: Path, exclude: str = "") -> str:
    """Zbiera treść istniejących plików MD projektu jako kontekst dla AI.

    Pomija plik `exclude` (ten który generujemy) i pliki readonly.
    Przycina każdy plik do 3000 znaków żeby nie przekroczyć limitu promptu.
    """
    parts: list[str] = []
    for fname in (*_DPS_CONVERTIBLE, "PLAN.md"):
        if fname == exclude:
            continue
        p = project_path / fname
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        snippet = content[:3000] + ("…(skrócono)" if len(content) > 3000 else "")
        parts.append(f"=== {fname} ===\n{snippet}")
    return "\n\n".join(parts) if parts else "(brak innych plików MD w projekcie)"


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


# Kolory statusów sesji CC w tab barze
_STATUS_COLOR_WORKING = QColor("#4ade80")   # zielony — CC pracuje
_STATUS_COLOR_WAITING = QColor("#fbbf24")   # żółty  — waiting/pauza
_STATUS_COLOR_OFFLINE = QColor("#f87171")   # czerwony — brak sesji


class _ColoredSlotTabBar(QTabBar):
    """QTabBar z kolorowym tłem per indeks i trzywierszową etykietą:
    wiersz 1: Projekt N
    wiersz 2: nazwa folderu
    wiersz 3: ikona + status + czas  (kolor zależny od fazy sesji)
    """

    def __init__(self, colors: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors = [QColor(c) for c in colors]
        self._sub_labels: list[str] = ["", "", "", ""]
        # (tekst_statusu, kolor_statusu) per slot
        self._status_labels: list[tuple[str, QColor]] = [
            ("", _STATUS_COLOR_OFFLINE),
            ("", _STATUS_COLOR_OFFLINE),
            ("", _STATUS_COLOR_OFFLINE),
            ("", _STATUS_COLOR_OFFLINE),
        ]
        self._hover_index = -1
        self.setMouseTracking(True)
        self.setExpanding(False)
        self.setDrawBase(False)

    def setSubLabel(self, index: int, text: str) -> None:
        if 0 <= index < len(self._sub_labels):
            self._sub_labels[index] = text or ""
            self.update()

    def setStatusLabel(self, index: int, phase: str | None, elapsed: str, is_missing: bool) -> None:
        """Ustaw wiersz statusu dla danego slotu."""
        if not (0 <= index < len(self._status_labels)):
            return
        if is_missing or not phase:
            text = "○  brak sesji"
            color = _STATUS_COLOR_OFFLINE
        elif phase == "working":
            text = f"⚙  working  {elapsed}"
            color = _STATUS_COLOR_WORKING
        elif phase == "waiting":
            text = f"⏸  waiting  {elapsed}"
            color = _STATUS_COLOR_WAITING
        else:
            text = f"●  {phase}  {elapsed}"
            color = _STATUS_COLOR_WAITING
        self._status_labels[index] = (text, color)
        self.update()

    def tabSizeHint(self, index: int) -> QSize:  # type: ignore[override]
        return QSize(200, 72)

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
        h3 = None  # wysokość jednej trzeciej, ustalana per zakładka
        for i in range(self.count()):
            color = self._colors[i] if i < len(self._colors) else QColor("#888888")
            rect = self.tabRect(i)
            is_selected = (i == self.currentIndex())
            is_hover = (i == self._hover_index)

            # Tło zakładki
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
            status_text, status_color = (
                self._status_labels[i] if i < len(self._status_labels)
                else ("", _STATUS_COLOR_OFFLINE)
            )

            h = rect.height()
            row_h = h // 3

            # Wiersz 1: nazwa projektu (Projekt N)
            r1 = QRect(rect.x() + 4, rect.y() + 2, rect.width() - 8, row_h)
            font_main = QFont("Segoe UI", 11)
            font_main.setBold(True)
            painter.setFont(font_main)
            painter.setPen(QColor("#000000") if is_selected else color.lighter(170))
            painter.drawText(r1, Qt.AlignmentFlag.AlignCenter, main_text)

            # Wiersz 2: nazwa folderu
            r2 = QRect(rect.x() + 4, rect.y() + row_h + 1, rect.width() - 8, row_h)
            font_sub = QFont("Segoe UI", 9)
            painter.setFont(font_sub)
            painter.setPen(QColor("#1a1a1a") if is_selected else color)
            if sub_text:
                metrics = painter.fontMetrics()
                elided = metrics.elidedText(sub_text, Qt.TextElideMode.ElideMiddle, rect.width() - 12)
                painter.drawText(r2, Qt.AlignmentFlag.AlignCenter, elided)

            # Wiersz 3: status sesji (ikona + faza + czas)
            r3 = QRect(rect.x() + 4, rect.y() + row_h * 2 + 1, rect.width() - 8, row_h - 2)
            # Pasek tła statusu
            status_bg = QColor(status_color)
            status_bg.setAlpha(50 if not is_selected else 80)
            painter.fillRect(r3, status_bg)
            font_st = QFont("Segoe UI", 8)
            painter.setFont(font_st)
            painter.setPen(QColor("#000000"))
            if status_text:
                metrics = painter.fontMetrics()
                elided = metrics.elidedText(status_text, Qt.TextElideMode.ElideRight, rect.width() - 10)
                painter.drawText(r3, Qt.AlignmentFlag.AlignCenter, elided)


def _render_conversation_html(messages: list[dict]) -> str:
    """Renderuje listę wiadomości {type, text, ts} jako HTML do QTextEdit."""
    import html as _html

    def _ts(msg: dict) -> str:
        ts = msg.get("ts")
        if ts is None:
            return ""
        try:
            return ts.strftime("%H:%M")
        except Exception:
            return ""

    parts = [
        "<html><body style='background:#0d0d0d;margin:0;padding:0;"
        "font-family:Consolas,monospace;font-size:13px;'>"
    ]
    for msg in messages:
        role = msg.get("type", "")
        text = _html.escape(msg.get("text", "").strip())
        ts_str = _ts(msg)
        text = text.replace("\n", "<br>")

        if role == "user":
            parts.append(
                f"<div style='"
                f"background:#0e1e2e;"
                f"border-left:3px solid #569cd6;"
                f"margin:6px 8px 2px 8px;"
                f"padding:6px 10px;"
                f"border-radius:0 4px 4px 0;'>"
                f"<span style='color:#569cd6;font-size:10px;font-weight:bold;'>"
                f"USER</span>"
                f"{'&nbsp;&nbsp;<span style=\"color:#3c5a7a;font-size:10px;\">' + ts_str + '</span>' if ts_str else ''}"
                f"<br><span style='color:#b0c8e0;'>{text}</span>"
                f"</div>"
            )
        else:
            parts.append(
                f"<div style='"
                f"background:#0d1a0d;"
                f"border-left:3px solid #4ec94e;"
                f"margin:2px 8px 6px 24px;"
                f"padding:6px 10px;"
                f"border-radius:0 4px 4px 0;'>"
                f"<span style='color:#4ec94e;font-size:10px;font-weight:bold;'>"
                f"CC</span>"
                f"{'&nbsp;&nbsp;<span style=\"color:#2a5a2a;font-size:10px;\">' + ts_str + '</span>' if ts_str else ''}"
                f"<br><span style='color:#c8e0c8;'>{text}</span>"
                f"</div>"
            )

    parts.append("</body></html>")
    return "".join(parts)


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
        # Aktualizuj wiersz statusu w tab barze
        s = snap.seconds_since_change
        mins = s // 60
        secs = s % 60
        elapsed = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
        self._slot_tab_bar.setStatusLabel(
            index=snap.slot_id - 1,
            phase=snap.phase,
            elapsed=elapsed,
            is_missing=snap.is_file_missing,
        )

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
