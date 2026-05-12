"""Panel 'Sesje CC' — uruchamianie i monitorowanie sesji Claude Code."""

from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QProcess, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolButton,
    QStyledItemDelegate,
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
    list_project_transcripts,
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
from src.ui.prompt_score_panel import PromptScorePanel as _PromptScorePanel
from src.ui.clean_clear_panel import CleanClearPanel as _CleanClearPanel
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

# SSM Monitor — lazy import
try:
    from src.ssm_module.views.ssm_tab import SsmTab as _SsmTab  # type: ignore
    _SSM_AVAILABLE = True
except ImportError:
    _SsmTab = None  # type: ignore
    _SSM_AVAILABLE = False

# SSC Converter — lazy import (wymaga SSC/src w sys.path, ustawianego przez main_window)
try:
    from cm.ssc_module.views.ssc_view import SscView as _SscView  # type: ignore
    _SSC_AVAILABLE = True
except ImportError:
    _SscView = None  # type: ignore
    _SSC_AVAILABLE = False
from src.watchers.session_watcher import (
    SessionWatcher,
    TerminalSnapshot,
    read_last_activity_ts,
    read_transcript_messages,
    read_transcript_tail,
)
from src.ui.projektant_panel import ExplorerSection, ReadmeSection, ChangelogSection

SLOT_COLORS = ["#2dd4bf", "#f97316", "#a78bfa", "#ef4444", "#8b8fa8", "#6e7288"]
SLOT_NAMES = ["Projekt 1", "Projekt 2", "Projekt 3", "Projekt 4", "Podgląd L", "Podgląd P"]

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


def _read_intake(project_path: str) -> dict | None:
    """Zwraca intake.json jako dict gdy folder jest projektem SSS v2, inaczej None."""
    try:
        p = Path(project_path) / "intake.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


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
    sss_detected = Signal(int, bool, str)   # slot_id, is_sss, project_name

    def __init__(self, slot_id: int, config: SlotConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slot_id = slot_id
        self._config = config
        self._color = SLOT_COLORS[slot_id - 1]
        self._plan_data: PlanData | None = None
        self._stats: ProjectStats | None = None
        self._history: SessionHistorySummary | None = None
        self._is_sss: bool = False
        self._sss_name: str = ""
        self._sesje_transcripts: list[tuple] = []

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._on_debounce)

        self._stop_pending = False
        self._git_init_then_round_end = False
        self._prompt_score_loaded = False
        # SSS state — inicjalizowane tutaj jako bezpieczne defaults (SSS workflow nieaktywny)
        self._sss_store = None
        self._sss_spawner = None
        self._sss_plan_watcher = None
        self._sss_round_watcher = None
        self._sss_active_session: str | None = None
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

        # Niewidoczne labele do trzymania danych snapshot (używane przez update_snapshot)
        self._lbl_phase = QLabel()
        self._lbl_model_live = QLabel()
        self._lbl_cost = QLabel()
        self._lbl_ctx = QLabel()

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

        self._tabs.addTab(self._build_config_monitor(), "Config")   # 0
        self._tabs.addTab(self._build_historia_logi(), "Historia")  # 1
        self._tabs.addTab(self._build_plan(), "ZADANIA")             # 2
        self._tabs.addTab(self._build_pcc(), "PLAN.md")              # 3
        self._tabs.addTab(self._build_md_file("CLAUDE.md"), "CLAUDE.md")
        self._tabs.addTab(self._build_md_file("ARCHITECTURE.md"), "ARCHITECTURE.md")
        self._tabs.addTab(self._build_md_file("CONVENTIONS.md"), "CONVENTIONS.md")
        self._tabs.addTab(self._build_full_converter(), "Full Converter")
        self._clean_clear = _CleanClearPanel(slot_color=self._color)
        self._tabs.addTab(self._clean_clear, "CleanClear")
        self._tabs.addTab(self._build_prompt_score(), "Prompt Score")

        self._explorer_section = ExplorerSection()
        self._tabs.addTab(self._explorer_section, "Explorer")

        self._readme_section = ReadmeSection()
        self._tabs.addTab(self._readme_section, "README.md")

        self._changelog_section = ChangelogSection()
        self._tabs.addTab(self._changelog_section, "CHANGELOG.md")

        root.addWidget(_sep())
        root.addWidget(self._build_action_bar())

    # ---- Dane ---------------------------------------------------------- #

    # ─────────────────────────────────────────────────────────────────────── #
    # Złożone zakładki (Config+Monitor, Historia+Logi)                        #
    # ─────────────────────────────────────────────────────────────────────── #

    def _build_config_monitor(self) -> QWidget:
        """Zewnętrzna zakładka 'Config' z wewnętrznym QTabWidget [Config][Monitor]."""
        inner = QTabWidget()
        inner.setDocumentMode(True)
        c = self._color
        inner.setStyleSheet(f"""
            QTabBar::tab {{
                background: {c}55;
                color: #0a0a0a;
                font-size: 10px;
                padding: 3px 10px;
                border: none;
                margin-right: 1px;
                border-radius: 2px 2px 0 0;
            }}
            QTabBar::tab:selected {{
                background: {c}99;
                color: #000000;
            }}
            QTabBar::tab:hover:!selected {{
                background: {c}77;
            }}
        """)
        inner.addTab(self._build_dane(), "Config")
        self._monitor_placeholder = self._build_ssm()
        inner.addTab(self._monitor_placeholder, "Monitor")
        self._inner_config_tabs = inner
        return inner

    def set_monitor_widget(self, mv: QWidget) -> None:
        """Podmienia zakładkę Monitor w wewnętrznym QTabWidget Config+Monitor."""
        inner = self._inner_config_tabs
        inner.removeTab(1)
        inner.insertTab(1, mv, "Monitor")

    def _build_historia_logi(self) -> QWidget:
        """Zewnętrzna zakładka 'Historia' z wewnętrznym QTabWidget [Historia][Logi]."""
        inner = QTabWidget()
        inner.setDocumentMode(True)
        c = self._color
        inner.setStyleSheet(f"""
            QTabBar::tab {{
                background: {c}55;
                color: #0a0a0a;
                font-size: 10px;
                padding: 3px 10px;
                border: none;
                margin-right: 1px;
                border-radius: 2px 2px 0 0;
            }}
            QTabBar::tab:selected {{
                background: {c}99;
                color: #000000;
            }}
            QTabBar::tab:hover:!selected {{
                background: {c}77;
            }}
        """)
        inner.addTab(self._build_historia_sesje_vibe(), "Historia")
        inner.addTab(self._build_logi(), "Logi")
        return inner

    # ─────────────────────────────────────────────────────────────────────── #

    def _build_dane(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle{background:#2a2a2a;}")

        # ── helpers ───────────────────────────────────────────────────
        def _row(key: str, widget: QWidget, key_w: int = 120) -> QHBoxLayout:
            r = QHBoxLayout()
            r.setSpacing(6)
            lbl = QLabel(key, styleSheet=_LBL_KEY)
            lbl.setFixedWidth(key_w)
            r.addWidget(lbl)
            r.addWidget(widget, stretch=1)
            return r

        def _sep() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.HLine)
            f.setStyleSheet("QFrame{color:#2a2a2a;margin:2px 0;}")
            return f

        # ══ LEWA KOLUMNA ══════════════════════════════════════════════
        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(10, 10, 6, 10)
        llay.setSpacing(5)

        # ── Ścieżka ───────────────────────────────────────────────────
        self._path_edit = QPlainTextEdit()
        self._path_edit.setFixedHeight(30)
        self._path_edit.setFont(_FONT_MONO)
        self._path_edit.setPlaceholderText("C:\\Projekty\\moj-projekt")
        self._btn_browse = QPushButton("…")
        self._btn_browse.setFixedWidth(26)
        self._btn_browse.setStyleSheet(_BTN)
        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        path_lbl = QLabel("Ścieżka:", styleSheet=_LBL_KEY)
        path_lbl.setFixedWidth(120)
        path_row.addWidget(path_lbl)
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(self._btn_browse)
        llay.addLayout(path_row)

        llay.addWidget(_sep())

        # ── Model / Effort / Uprawnienia ──────────────────────────────
        self._model_combo = QComboBox()
        self._model_combo.addItems(CC_MODELS)
        self._model_combo.setFont(_FONT_MONO)
        llay.addLayout(_row("Model:", self._model_combo))

        self._effort_combo = QComboBox()
        self._effort_combo.addItems(CC_EFFORTS)
        self._effort_combo.setFont(_FONT_MONO)
        llay.addLayout(_row("Effort:", self._effort_combo))

        self._perm_combo = QComboBox()
        self._perm_combo.addItems(list(CC_PERMISSION_MODES.keys()))
        self._perm_combo.setFont(_FONT_MONO)
        llay.addLayout(_row("Uprawnienia:", self._perm_combo))

        # ── Tryb sesji ────────────────────────────────────────────────
        self._session_mode_group = QButtonGroup(self)
        session_widget = QWidget()
        session_inner = QHBoxLayout(session_widget)
        session_inner.setContentsMargins(0, 0, 0, 0)
        session_inner.setSpacing(10)
        for i, (label, tip) in enumerate([
            ("Nowa",      "Zawsze startuje nową sesję CC w projekcie"),
            ("Wznów",     "--resume: wznawia ostatnią przerwaną sesję (zachowuje kontekst)"),
            ("Kontynuuj", "--continue: kontynuuje ostatnią rozmowę bez interakcji użytkownika"),
        ]):
            rb = QRadioButton(label)
            rb.setStyleSheet("color:#cccccc;font-size:10px;")
            rb.setToolTip(tip)
            self._session_mode_group.addButton(rb, i)
            session_inner.addWidget(rb)
            if i == 0:
                rb.setChecked(True)
        session_inner.addStretch()
        llay.addLayout(_row("Tryb sesji:", session_widget))

        # ── Opcje ────────────────────────────────────────────────────
        self._chk_verbose = QCheckBox("Verbose  (--verbose)")
        self._chk_verbose.setStyleSheet("color:#cccccc;font-size:10px;")
        self._chk_verbose.setToolTip("--verbose — szczegółowe logi CC w terminalu.")
        self._chk_no_update = QCheckBox("Bez aktualizacji  (--no-update-check)")
        self._chk_no_update.setStyleSheet("color:#cccccc;font-size:10px;")
        self._chk_no_update.setToolTip("--no-update-check — pomija sprawdzanie aktualizacji, przyspiesza start.")
        self._chk_no_flicker = QCheckBox("No Flicker  (CLAUDE_CODE_NO_FLICKER=1)")
        self._chk_no_flicker.setStyleSheet("color:#cccccc;font-size:10px;")
        self._chk_no_flicker.setToolTip(
            "Ustawia CLAUDE_CODE_NO_FLICKER=1 w środowisku terminala.\n"
            "Eliminuje migotanie przy starcie CC w VS Code."
        )
        self._chk_focus = QCheckBox("/focus  (prompt startowy)")
        self._chk_focus.setStyleSheet("color:#cccccc;font-size:10px;")
        self._chk_focus.setToolTip(
            "Dodaje /focus na początku promptu startowego.\n"
            "Wymusza tryb skupienia w CC po uruchomieniu."
        )
        opts_widget = QWidget()
        opts_inner = QHBoxLayout(opts_widget)
        opts_inner.setContentsMargins(0, 0, 0, 0)
        opts_inner.setSpacing(14)
        opts_inner.addWidget(self._chk_verbose)
        opts_inner.addWidget(self._chk_no_update)
        opts_inner.addWidget(self._chk_no_flicker)
        opts_inner.addWidget(self._chk_focus)
        opts_inner.addStretch()
        llay.addLayout(_row("Opcje:", opts_widget))

        llay.addWidget(_sep())

        # ── Komenda przed CC ──────────────────────────────────────────
        self._pre_cmd_edit = QPlainTextEdit()
        self._pre_cmd_edit.setFixedHeight(30)
        self._pre_cmd_edit.setFont(_FONT_MONO)
        self._pre_cmd_edit.setPlaceholderText("np. & \".venv\\Scripts\\Activate.ps1\"")
        self._pre_cmd_edit.setToolTip(
            "Wykonywana w terminalu zanim zostanie wywołane cc.\n"
            "Sekwencja: [ta komenda] → cc [flagi] → [prompt]"
        )
        llay.addLayout(_row("Przed CC:", self._pre_cmd_edit))

        # ── Dodatkowe flagi ───────────────────────────────────────────
        self._cc_flags_edit = QPlainTextEdit()
        self._cc_flags_edit.setFixedHeight(30)
        self._cc_flags_edit.setFont(_FONT_MONO)
        self._cc_flags_edit.setPlaceholderText("np. --add-dir C:\\Shared  lub  --output-format stream-json")
        self._cc_flags_edit.setToolTip(
            "Dodatkowe flagi CLI dla cc — trafiają za Model/Effort/Uprawnienia/Tryb.\n"
            "Przykłady: --add-dir /ścieżka   --output-format stream-json"
        )
        llay.addLayout(_row("Flagi CC:", self._cc_flags_edit))

        llay.addWidget(_sep())

        # ── Prompt startowy ───────────────────────────────────────────
        prompt_hdr = QHBoxLayout()
        prompt_hdr.addWidget(QLabel("Prompt startowy:", styleSheet=_LBL_KEY))
        prompt_hdr.addStretch()
        btn_reset = QPushButton("Resetuj")
        btn_reset.setStyleSheet(_BTN)
        btn_reset.setFixedWidth(60)
        btn_reset.clicked.connect(lambda: self._vibe_edit.setPlainText(DEFAULT_VIBE_PROMPT))
        btn_copy = QPushButton("Kopiuj")
        btn_copy.setStyleSheet(_BTN)
        btn_copy.setFixedWidth(52)
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self._vibe_edit.toPlainText()))
        prompt_hdr.addWidget(btn_reset)
        prompt_hdr.addWidget(btn_copy)
        llay.addLayout(prompt_hdr)

        self._vibe_edit = QPlainTextEdit()
        self._vibe_edit.setFont(_FONT_MONO)
        self._vibe_edit.setPlaceholderText(DEFAULT_VIBE_PROMPT)
        llay.addWidget(self._vibe_edit, stretch=1)

        # ══ PRAWA KOLUMNA — Statystyki ════════════════════════════════
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(6, 10, 10, 10)
        rlay.setSpacing(5)

        stats_hdr = QHBoxLayout()
        stats_hdr.addWidget(QLabel("Statystyki projektu", styleSheet=_LBL_HEAD))
        stats_hdr.addStretch()
        self._btn_stats_refresh = QPushButton("⟳")
        self._btn_stats_refresh.setFixedWidth(26)
        self._btn_stats_refresh.setStyleSheet(_BTN)
        stats_hdr.addWidget(self._btn_stats_refresh)
        rlay.addLayout(stats_hdr)

        rlay.addWidget(_sep())

        self._lbl_files = _val()
        self._lbl_size = _val()
        self._lbl_git = _val()
        self._lbl_git_url = _val()
        self._lbl_branch = _val()
        for key, lbl in [
            ("Pliki/foldery:", self._lbl_files),
            ("Rozmiar:", self._lbl_size),
            ("Git:", self._lbl_git),
            ("Remote:", self._lbl_git_url),
            ("Gałąź:", self._lbl_branch),
        ]:
            rlay.addLayout(_row(key, lbl, key_w=100))

        rlay.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([600, 300])

        root.addWidget(splitter)
        return w

    # ---- PLAN ---------------------------------------------------------- #

    # ---- ZADANIA -------------------------------------------------------- #

    def _build_plan(self) -> QWidget:
        """Zakładka ZADANIA — generowanie zadań do PLAN.md przez CC."""
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle{background:#2a2a2a;}")

        # ══ LEWA: Opis zamierzenia + kontrolki ════════════════════════
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 6, 10)
        ll.setSpacing(6)

        ll.addWidget(QLabel(
            "Opisz co chcesz osiągnąć:",
            styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;",
        ))

        self._zadania_intent = QPlainTextEdit()
        self._zadania_intent.setFont(_FONT_MONO)
        self._zadania_intent.setPlaceholderText(
            "np. Chcę dodać obsługę motywów kolorystycznych — jasny i ciemny.\n"
            "Użytkownik powinien móc przełączać motyw w ustawieniach.\n"
            "Motyw ma być pamiętany między sesjami."
        )
        ll.addWidget(self._zadania_intent, stretch=1)

        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:", styleSheet="color:#6c7086;font-size:10px;"))
        self._zadania_model = QComboBox()
        self._zadania_model.addItems(CC_MODELS)
        self._zadania_model.setFont(_FONT_MONO)
        self._zadania_model.setCurrentText("claude-sonnet-4-6")
        model_row.addWidget(self._zadania_model, stretch=1)
        ll.addLayout(model_row)

        # Status
        self._zadania_status = QLabel("")
        self._zadania_status.setStyleSheet("color:#585b70;font-size:10px;")
        self._zadania_status.setWordWrap(True)
        ll.addWidget(self._zadania_status)

        # Przycisk Generuj
        self._btn_zadania_gen = QPushButton("▶  Generuj zadania przez CC")
        self._btn_zadania_gen.setStyleSheet(_BTN_ACCENT)
        self._btn_zadania_gen.setFont(_FONT_MONO)
        self._btn_zadania_gen.clicked.connect(self._on_zadania_generate)
        ll.addWidget(self._btn_zadania_gen)

        self._btn_zadania_stop = QPushButton("■  Stop")
        self._btn_zadania_stop.setStyleSheet(_BTN_DANGER)
        self._btn_zadania_stop.setFont(_FONT_MONO)
        self._btn_zadania_stop.setEnabled(False)
        self._btn_zadania_stop.clicked.connect(self._on_zadania_stop)
        ll.addWidget(self._btn_zadania_stop)

        splitter.addWidget(left)

        # ══ PRAWA: wyniki podzielone na pół pionowo ═══════════════════
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 10, 10, 10)
        rl.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setHandleWidth(2)
        right_splitter.setStyleSheet("QSplitter::handle{background:#2a2a2a;}")

        # Góra: lista wygenerowanych zadań
        tasks_w = QWidget()
        tl = QVBoxLayout(tasks_w)
        tl.setContentsMargins(0, 0, 0, 6)
        tl.setSpacing(4)
        tasks_hdr = QHBoxLayout()
        tasks_hdr.addWidget(QLabel("Wygenerowane zadania:", styleSheet="color:#9cdcfe;font-size:10px;font-weight:bold;"))
        tasks_hdr.addStretch()
        self._btn_zadania_save = QPushButton("✓  Zapisz do PLAN.md")
        self._btn_zadania_save.setStyleSheet(_BTN_GREEN)
        self._btn_zadania_save.setFont(_FONT_MONO)
        self._btn_zadania_save.setEnabled(False)
        self._btn_zadania_save.clicked.connect(self._on_zadania_save)
        tasks_hdr.addWidget(self._btn_zadania_save)
        tl.addLayout(tasks_hdr)

        self._zadania_list = QPlainTextEdit()
        self._zadania_list.setFont(_FONT_MONO)
        self._zadania_list.setReadOnly(False)
        self._zadania_list.setStyleSheet(
            "QPlainTextEdit{background:#1e1e2e;color:#cdd6f4;"
            "border:1px solid #313244;border-radius:3px;padding:6px;}"
        )
        self._zadania_list.setPlaceholderText(
            "Tutaj pojawią się zadania wygenerowane przez CC.\n"
            "Możesz je edytować przed zapisaniem do PLAN.md."
        )
        tl.addWidget(self._zadania_list, stretch=1)
        right_splitter.addWidget(tasks_w)

        # Dół: log CC
        log_w = QWidget()
        logl = QVBoxLayout(log_w)
        logl.setContentsMargins(0, 6, 0, 0)
        logl.setSpacing(2)
        logl.addWidget(QLabel("Log CC:", styleSheet="color:#6c7086;font-size:9px;font-weight:bold;letter-spacing:1px;"))
        self._zadania_log = QPlainTextEdit()
        self._zadania_log.setReadOnly(True)
        self._zadania_log.setFont(QFont("Consolas", 8))
        self._zadania_log.setStyleSheet(
            "QPlainTextEdit{background:#13131e;color:#585b70;"
            "border:none;border-radius:3px;padding:6px;}"
        )
        logl.addWidget(self._zadania_log, stretch=1)
        right_splitter.addWidget(log_w)

        right_splitter.setSizes([300, 150])
        rl.addWidget(right_splitter, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([380, 420])

        root.addWidget(splitter, stretch=1)

        # Stan wewnętrzny
        self._zadania_process: QProcess | None = None
        self._zadania_buffer: str = ""

        return w

    _ZADANIA_SYSTEM = (
        "Jesteś asystentem programistycznym. Na podstawie kontekstu projektu "
        "i opisu zamierzenia użytkownika wygeneruj konkretną listę zadań "
        "do dodania do sekcji 'next' w PLAN.md.\n\n"
        "Zasady:\n"
        "- Każde zadanie to jedna linia w formacie: - [ ] treść zadania\n"
        "- Zadania mają być konkretne, atomowe i wykonalne przez programistę\n"
        "- Nie dodawaj żadnego wstępu ani podsumowania — TYLKO lista - [ ] ...\n"
        "- Nie używaj nagłówków ani sekcji — tylko linie - [ ] ...\n"
        "- Liczba zadań: 3–10 zależnie od złożoności zamierzenia"
    )

    def _zadania_build_prompt(self, path: str, intent: str) -> str:
        p = Path(path)
        parts = [f"# Opis zamierzenia\n{intent.strip()}\n"]
        for fname in ("CLAUDE.md", "PLAN.md", "ARCHITECTURE.md"):
            fp = p / fname
            if fp.exists():
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")[:4000]
                    parts.append(f"# {fname}\n{content}")
                except OSError:
                    pass
        return "\n\n".join(parts)

    def _on_zadania_generate(self) -> None:
        path = self._path_edit.toPlainText().strip()
        intent = self._zadania_intent.toPlainText().strip()

        if not path or not Path(path).is_dir():
            self._zadania_status.setText("⚠ Ustaw ścieżkę projektu w zakładce Config.")
            self._zadania_status.setStyleSheet("color:#f38ba8;font-size:10px;")
            return
        if not intent:
            self._zadania_status.setText("⚠ Opisz zamierzenie przed generowaniem.")
            self._zadania_status.setStyleSheet("color:#f38ba8;font-size:10px;")
            return

        import shutil as _shutil
        import sys as _sys
        cc = _shutil.which("cc") or _shutil.which("claude")
        if not cc:
            self._zadania_status.setText("⚠ Nie znaleziono komendy cc / claude w PATH.")
            self._zadania_status.setStyleSheet("color:#f38ba8;font-size:10px;")
            return

        self._zadania_buffer = ""
        self._zadania_log.clear()
        self._zadania_list.clear()
        self._zadania_list.setReadOnly(True)
        self._btn_zadania_gen.setEnabled(False)
        self._btn_zadania_stop.setEnabled(True)
        self._btn_zadania_save.setEnabled(False)
        self._zadania_status.setText("● Analizuję projekt i generuję zadania…")
        self._zadania_status.setStyleSheet("color:#f9c74f;font-size:10px;")

        model = self._zadania_model.currentText()
        prompt = self._zadania_build_prompt(path, intent)
        full_prompt = f"{self._ZADANIA_SYSTEM}\n\n{prompt}"

        self._zadania_process = QProcess(self)
        self._zadania_process.setWorkingDirectory(path)
        self._zadania_process.readyReadStandardOutput.connect(self._zadania_on_stdout)
        self._zadania_process.readyReadStandardError.connect(self._zadania_on_stderr)
        self._zadania_process.finished.connect(self._zadania_on_finished)

        import sys as _sys

        cc_args = ["--print", "--output-format", "stream-json", "--verbose", "--model", model]

        # Środowisko wyizolowane od bieżącej sesji CC — bez CC_PANEL_TERMINAL_ID
        env = self._zadania_process.processEnvironment()
        env.remove("CC_PANEL_TERMINAL_ID")
        env.remove("CLAUDE_SESSION_ID")
        self._zadania_process.setProcessEnvironment(env)

        # Na Windows .cmd/.bat wymagają pośrednictwa cmd.exe.
        # cmd /c traktuje cały string jako jedną komendę — ścieżka BEZ cudzysłowów wewnętrznych.
        if _sys.platform == "win32" and cc.lower().endswith((".cmd", ".bat")):
            args_str = " ".join(cc_args)
            self._zadania_process.setProgram("cmd")
            self._zadania_process.setArguments(["/c", f'{cc} {args_str}'])
        else:
            self._zadania_process.setProgram(cc)
            self._zadania_process.setArguments(cc_args)

        self._zadania_process.start()
        if not self._zadania_process.waitForStarted(5000):
            self._zadania_status.setText("✗ Nie udało się uruchomić CC.")
            self._zadania_status.setStyleSheet("color:#f38ba8;font-size:10px;")
            self._zadania_process = None
            self._btn_zadania_gen.setEnabled(True)
            self._btn_zadania_stop.setEnabled(False)
            return

        self._zadania_process.write(full_prompt.encode("utf-8"))
        self._zadania_process.closeWriteChannel()

    def _zadania_on_stdout(self) -> None:
        if not self._zadania_process:
            return
        raw = bytes(self._zadania_process.readAllStandardOutput()).decode("utf-8", errors="replace")
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
                    self._zadania_buffer += chunk
                    # Aktualizuj listę live — pokaż linie - [ ] na bieżąco
                    tasks = [l for l in self._zadania_buffer.splitlines() if l.strip().startswith("- [ ]")]
                    if tasks:
                        self._zadania_list.setPlainText("\n".join(tasks))
            except (json.JSONDecodeError, KeyError):
                self._zadania_log.appendPlainText(line)

    def _zadania_on_stderr(self) -> None:
        if not self._zadania_process:
            return
        raw = bytes(self._zadania_process.readAllStandardError()).decode("utf-8", errors="replace")
        if raw.strip():
            self._zadania_log.appendPlainText(f"[stderr] {raw.strip()}")

    def _zadania_on_finished(self, exit_code: int, _status) -> None:
        self._btn_zadania_gen.setEnabled(True)
        self._btn_zadania_stop.setEnabled(False)
        self._zadania_process = None

        tasks = [l.rstrip() for l in self._zadania_buffer.splitlines() if l.strip().startswith("- [ ]")]
        if tasks and exit_code == 0:
            self._zadania_list.setPlainText("\n".join(tasks))
            self._zadania_list.setReadOnly(False)
            self._btn_zadania_save.setEnabled(True)
            self._zadania_status.setText(f"✓ Wygenerowano {len(tasks)} zadań. Możesz je edytować przed zapisem.")
            self._zadania_status.setStyleSheet("color:#a6e3a1;font-size:10px;")
        elif exit_code != 0:
            self._zadania_status.setText(f"✗ CC zakończyło z błędem (kod {exit_code}).")
            self._zadania_status.setStyleSheet("color:#f38ba8;font-size:10px;")
            self._zadania_list.setReadOnly(False)
        else:
            self._zadania_status.setText("⚠ CC nie wygenerowało żadnych zadań w formacie - [ ] ...")
            self._zadania_status.setStyleSheet("color:#f9c74f;font-size:10px;")
            self._zadania_log.appendPlainText(f"\n--- pełna odpowiedź ---\n{self._zadania_buffer}")
            self._zadania_list.setReadOnly(False)

    def _on_zadania_stop(self) -> None:
        if self._zadania_process:
            self._zadania_process.kill()
        self._btn_zadania_gen.setEnabled(True)
        self._btn_zadania_stop.setEnabled(False)
        self._zadania_status.setText("■ Przerwano.")
        self._zadania_status.setStyleSheet("color:#585b70;font-size:10px;")

    def _on_zadania_save(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if not path:
            return
        plan_path = Path(path) / "PLAN.md"
        tasks_text = self._zadania_list.toPlainText().strip()
        if not tasks_text:
            return

        # Zbierz linie - [ ] z pola (user mógł edytować)
        new_tasks = [l.rstrip() for l in tasks_text.splitlines() if l.strip().startswith("- [ ]")]
        if not new_tasks:
            self._zadania_status.setText("⚠ Brak linii - [ ] do zapisania.")
            self._zadania_status.setStyleSheet("color:#f9c74f;font-size:10px;")
            return

        try:
            if plan_path.exists():
                text = plan_path.read_text(encoding="utf-8")
                from src.projektant.template_parser import read_section, write_section
                # Sprawdź czy mamy sekcję next w formacie PCC
                existing = read_section(text, "next") or ""
                existing_lines = [l.rstrip() for l in existing.splitlines() if l.strip()]
                all_tasks = existing_lines + new_tasks
                new_body = "\n".join(all_tasks) + "\n"
                try:
                    updated = write_section(text, "next", new_body)
                    plan_path.write_text(updated, encoding="utf-8")
                    self._zadania_status.setText(
                        f"✓ Dodano {len(new_tasks)} zadań do PLAN.md (sekcja next)."
                    )
                except ValueError:
                    # Brak sekcji PCC — dołącz na końcu pliku
                    plan_path.write_text(
                        text.rstrip() + "\n\n## Next\n" + "\n".join(new_tasks) + "\n",
                        encoding="utf-8",
                    )
                    self._zadania_status.setText(
                        f"✓ Dodano {len(new_tasks)} zadań do PLAN.md (sekcja ## Next)."
                    )
            else:
                # Brak PLAN.md — utwórz minimalny
                plan_path.write_text(
                    "## Next\n" + "\n".join(new_tasks) + "\n",
                    encoding="utf-8",
                )
                self._zadania_status.setText(
                    f"✓ Utworzono PLAN.md z {len(new_tasks)} zadaniami."
                )
            self._zadania_status.setStyleSheet("color:#a6e3a1;font-size:10px;")
            self._btn_zadania_save.setEnabled(False)
            # Odśwież widok PCC jeśli załadowany
            self.reload_pcc()
        except OSError as e:
            self._zadania_status.setText(f"✗ Błąd zapisu: {e}")
            self._zadania_status.setStyleSheet("color:#f38ba8;font-size:10px;")

    # ---- PROMPT SCORE -------------------------------------------------- #

    def _build_prompt_score(self) -> QWidget:
        """Osadzony PromptScorePanel — wyświetla PS.md projektu SSS."""
        self._prompt_score = _PromptScorePanel(slot_color=self._color)
        return self._prompt_score

    # ---- Monitor (Stan sesji + SSS Monitor) ---------------------------- #

    def _build_monitor(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # ── Stan aktywnej sesji ────────────────────────────────────────
        stan = QFrame()
        stan.setStyleSheet(_CARD)
        sl = QHBoxLayout(stan)
        sl.setContentsMargins(10, 6, 10, 6)
        sl.setSpacing(24)
        sl.addWidget(QLabel("Stan aktywnej sesji", styleSheet=_LBL_HEAD))
        sl.addWidget(QLabel("·", styleSheet=_LBL_DIM))
        self._lbl_phase = _val()
        self._lbl_model_live = _val()
        self._lbl_cost = _val()
        self._lbl_ctx = _val()
        for label, widget in (
            ("Faza:", self._lbl_phase),
            ("Model:", self._lbl_model_live),
            ("Koszt:", self._lbl_cost),
            ("Ctx%:", self._lbl_ctx),
        ):
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl_k = QLabel(label, styleSheet=_LBL_KEY)
            row.addWidget(lbl_k)
            row.addWidget(widget)
            sl.addLayout(row)
        sl.addStretch()
        lay.addWidget(stan)

        # ── SSS Monitor (SsmTab) ───────────────────────────────────────
        if not _SSM_AVAILABLE or _SsmTab is None:
            lbl = QLabel("Moduł SSM (Monitor) niedostępny.")
            lbl.setStyleSheet("color:#5c6370;font-size:11px;")
            lay.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            self._ssm_widget = _SsmTab()
            lay.addWidget(self._ssm_widget, stretch=1)
        return w

    def _build_ssm(self) -> QWidget:
        """Placeholder — CCLauncherPanel podmienia tę zakładkę na wspólny _MonitorView."""
        w = QWidget()
        w.setObjectName("_monitor_placeholder")
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

    def _on_sss_resume(self, project_dir_str: str) -> None:
        try:
            project_dir = Path(project_dir_str)
            session_id, project_dir = self._sss_spawner.resume(project_dir)
            self._sss_store.insert_event(session_id, "resume", payload={
                "project_dir": str(project_dir),
            })
            self._sss_logs.refresh_sessions()
            self._sss_start_watchers(project_dir, session_id)
        except Exception as exc:
            QMessageBox.critical(self, "SSS — błąd wznowienia", str(exc))

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

        # ── Pasek narzędzi (wspólny dla obu zakładek) ──────────────────
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        self._pcc_path_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._pcc_path_lbl.setFont(_FONT_MONO)
        toolbar.addWidget(self._pcc_path_lbl, stretch=1)

        # przyciski widoku PCC
        btn_refresh = QPushButton("⟳  Odśwież")
        btn_refresh.setStyleSheet(_BTN)
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self.reload_pcc)
        toolbar.addWidget(btn_refresh)

        # przyciski edytora (widoczne tylko w zakładce Edytor)
        self._lbl_plan_path = QLabel("", styleSheet=_LBL_DIM)
        self._lbl_plan_path.setFont(_FONT_MONO)
        self._lbl_plan_path.hide()
        self._btn_plan_refresh = QPushButton("Odśwież")
        self._btn_plan_refresh.setStyleSheet(_BTN)
        self._btn_plan_refresh.hide()
        self._btn_plan_save = QPushButton("Zapisz")
        self._btn_plan_save.setStyleSheet(_BTN)
        self._btn_plan_save.setEnabled(False)
        self._btn_plan_save.hide()
        toolbar.addWidget(self._btn_plan_refresh)
        toolbar.addWidget(self._btn_plan_save)
        outer.addLayout(toolbar)

        # ── Wewnętrzny QTabWidget: Widok | Edytor ─────────────────────
        inner_tabs = QTabWidget()
        inner_tabs.setDocumentMode(True)
        inner_tabs.setStyleSheet(f"""
            QTabBar::tab {{
                background:#1a1a1a; color:#5c6370;
                font-size:10px; padding:4px 14px;
                border:none; margin-right:2px;
            }}
            QTabBar::tab:selected {{
                background:#1e1e1e; color:{self._color};
                border-bottom:2px solid {self._color};
            }}
            QTabBar::tab:hover:!selected {{ background:#222222; color:#9d9d9d; }}
        """)

        def _on_inner_tab(idx: int) -> None:
            is_editor = (idx == 1)
            self._btn_plan_refresh.setVisible(is_editor)
            self._btn_plan_save.setVisible(is_editor)
            btn_refresh.setVisible(not is_editor)

        inner_tabs.currentChanged.connect(_on_inner_tab)
        outer.addWidget(inner_tabs, stretch=1)

        # ── Zakładka 0: Widok (sekcje PCC) ────────────────────────────
        view_w = QWidget()
        view_root = QVBoxLayout(view_w)
        view_root.setContentsMargins(0, 0, 0, 0)
        view_root.setSpacing(0)

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
        view_root.addWidget(scroll, stretch=1)
        inner_tabs.addTab(view_w, "Widok")

        # ── Zakładka 1: Edytor surowy PLAN.md ─────────────────────────
        editor_w = QWidget()
        editor_lay = QVBoxLayout(editor_w)
        editor_lay.setContentsMargins(6, 6, 6, 6)
        editor_lay.setSpacing(4)

        summary = QFrame()
        summary.setStyleSheet(_CARD)
        s_lay = QVBoxLayout(summary)
        s_lay.setContentsMargins(8, 6, 8, 6)
        s_lay.setSpacing(3)
        self._lbl_plan_stan = QLabel("Stan: —", styleSheet=_LBL_VAL, wordWrap=True)
        self._lbl_plan_active = QLabel("Aktywne: —", styleSheet=_LBL_VAL, wordWrap=True)
        s_lay.addWidget(self._lbl_plan_stan)
        s_lay.addWidget(self._lbl_plan_active)
        editor_lay.addWidget(summary)

        self._plan_editor = QPlainTextEdit()
        self._plan_editor.setFont(_FONT_MONO)
        self._plan_editor.setPlaceholderText(
            "Brak pliku PLAN.md lub nie ustawiono ścieżki projektu."
        )
        editor_lay.addWidget(self._plan_editor, stretch=1)
        inner_tabs.addTab(editor_w, "Edytor")

        return w

    # ---- Logi ---------------------------------------------------------- #

    _CC_PROJECTS_DIR = Path.home() / ".claude" / "projects"

    # Indeksy stron w QStackedWidget zakładki Logi
    _LOGI_PAGE_PLAIN = 0   # non-SSS: surowy transkrypt
    _LOGI_PAGE_SSS   = 1   # SSS v2/v3: transkrypt + karty statusu projektu

    def _build_logi(self) -> QWidget:
        """Zakładka Logi — transkrypt sesji CC z widokiem adaptowanym do SSS/non-SSS."""
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        # ── Nagłówek wspólny ────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._logi_title_lbl = QLabel("Transkrypt sesji CC", styleSheet=_LBL_HEAD)
        hdr.addWidget(self._logi_title_lbl)
        hdr.addStretch()
        self._logi_type_badge = QLabel("")
        self._logi_type_badge.setStyleSheet(
            "background:#252526;color:#5c6370;border-radius:3px;"
            "padding:2px 8px;font-size:10px;"
        )
        self._logi_type_badge.setVisible(False)
        hdr.addWidget(self._logi_type_badge)
        self._jsonl_file_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._jsonl_file_lbl.setFont(_FONT_SMALL)
        hdr.addWidget(self._jsonl_file_lbl)
        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedWidth(28)
        btn_refresh.setStyleSheet(_BTN)
        btn_refresh.clicked.connect(self.reload_jsonl_transcript)
        hdr.addWidget(btn_refresh)
        root.addLayout(hdr)

        # ── QStackedWidget: dwie strony ──────────────────────────────────
        self._logi_stack = QStackedWidget()

        # Strona 0 — non-SSS: samo pole tekstowe z transkryptem
        self._jsonl_view = QTextEdit()
        self._jsonl_view.setReadOnly(True)
        self._jsonl_view.setFont(_FONT_MONO)
        self._jsonl_view.setStyleSheet(
            "QTextEdit{background:#0d1117;border:1px solid #3c3c3c;border-radius:3px;padding:6px}"
        )
        self._jsonl_view.setPlaceholderText(
            "(brak pliku sesji — uruchom sesję CC dla tego projektu)"
        )
        self._logi_stack.addWidget(self._jsonl_view)

        # Strona 1 — SSS: splitter z kartami statusu (góra) + transkrypt (dół)
        sss_page = QWidget()
        sss_page.setStyleSheet("background:#141414;")
        sss_lay = QVBoxLayout(sss_page)
        sss_lay.setContentsMargins(0, 0, 0, 0)
        sss_lay.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#2a2a2a;height:4px;}"
        )

        # Górna część — karty statusu SSS
        self._logi_sss_status = QWidget()
        self._logi_sss_status.setStyleSheet("background:#141414;")
        self._logi_sss_status_lay = QHBoxLayout(self._logi_sss_status)
        self._logi_sss_status_lay.setContentsMargins(0, 4, 0, 4)
        self._logi_sss_status_lay.setSpacing(8)
        self._logi_sss_status_lay.addStretch()
        self._logi_sss_status.setMaximumHeight(120)
        splitter.addWidget(self._logi_sss_status)

        # Dolna część — transkrypt SSS (ta sama paleta, inny widget)
        self._jsonl_view_sss = QTextEdit()
        self._jsonl_view_sss.setReadOnly(True)
        self._jsonl_view_sss.setFont(_FONT_MONO)
        self._jsonl_view_sss.setStyleSheet(
            "QTextEdit{background:#0d1117;border:1px solid #3c3c3c;border-radius:3px;padding:6px}"
        )
        self._jsonl_view_sss.setPlaceholderText(
            "(brak pliku sesji — uruchom sesję CC dla tego projektu)"
        )
        splitter.addWidget(self._jsonl_view_sss)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        sss_lay.addWidget(splitter, stretch=1)
        self._logi_stack.addWidget(sss_page)

        root.addWidget(self._logi_stack, stretch=1)

        # ── Watcher na katalog projektów CC ──────────────────────────────
        self._jsonl_watcher = QFileSystemWatcher(w)
        self._jsonl_watcher.fileChanged.connect(self._on_jsonl_changed)
        self._jsonl_watcher.directoryChanged.connect(self._on_jsonl_dir_changed)

        return w

    # -- Detekcja SSS -----------------------------------------------------

    @staticmethod
    def _detect_sss_version(project_path: str) -> str | None:
        """Zwraca 'v3', 'v2' lub None gdy projekt nie jest SSS."""
        if not project_path:
            return None
        p = Path(project_path)
        # v3: PS.md + PLAN.md z markerem SECTION:next
        if (p / "PS.md").exists():
            plan = p / "PLAN.md"
            if plan.exists():
                try:
                    if "<!-- SECTION:next -->" in plan.read_text(encoding="utf-8", errors="ignore"):
                        return "v3"
                except Exception:
                    pass
            return "v3"  # PS.md samo w sobie wystarczy jako sygnał v3
        # v2: intake.json
        if (p / "intake.json").exists():
            return "v2"
        # Fallback: PLAN.md z markerem
        plan = p / "PLAN.md"
        if plan.exists():
            try:
                if "<!-- SECTION:next -->" in plan.read_text(encoding="utf-8", errors="ignore"):
                    return "v3"
            except Exception:
                pass
        return None

    # -- Widok SSS — karty statusu ----------------------------------------

    def _rebuild_sss_status_cards(self, project_path: str, sss_version: str) -> None:
        """Czyści i odbudowuje karty statusu SSS w górnej części widoku Logi."""
        lay = self._logi_sss_status_lay
        # Usuń wszystkie widgety poza końcowym stretch
        while lay.count() > 1:
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        p = Path(project_path)

        # Karta: wersja SSS
        lay.insertWidget(lay.count() - 1, self._make_logi_card(
            "SSS", sss_version,
            "#98c379" if sss_version == "v3" else "#e5c07b",
            sub="Scripted Skills System",
        ))

        # Karta: status PLAN.md
        plan_status, plan_task, plan_session = self._read_plan_status(p)
        lay.insertWidget(lay.count() - 1, self._make_logi_card(
            "PLAN", plan_status or "—",
            "#61afef",
            sub=f"sesja {plan_session}" if plan_session else plan_task or "",
        ))

        # Karta: PS.md (tylko v3)
        if sss_version == "v3":
            ps_status, ps_score = self._read_ps_status(p)
            lay.insertWidget(lay.count() - 1, self._make_logi_card(
                "PS", ps_status or "—",
                "#c678dd" if ps_status == "scored" else "#5c6370",
                sub=ps_score,
            ))

        # Karta: liczba sesji CC
        n_sessions = self._count_cc_sessions(project_path)
        lay.insertWidget(lay.count() - 1, self._make_logi_card(
            "Sesje CC", str(n_sessions) if n_sessions is not None else "—",
            "#56b6c2",
            sub="pliki .jsonl",
        ))

    @staticmethod
    def _make_logi_card(title: str, value: str, color: str, sub: str = "") -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:#1e1e1e;border:1px solid {color}33;"
            "border-radius:4px;min-width:90px;max-width:160px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color:#5c6370;font-size:9px;background:transparent;border:none;")
        lay.addWidget(t_lbl)

        v_lbl = QLabel(value)
        v_lbl.setStyleSheet(
            f"color:{color};font-size:13px;font-weight:bold;"
            "background:transparent;border:none;"
        )
        lay.addWidget(v_lbl)

        if sub:
            s_lbl = QLabel(sub)
            s_lbl.setStyleSheet("color:#4a4a5a;font-size:9px;background:transparent;border:none;")
            s_lbl.setWordWrap(True)
            lay.addWidget(s_lbl)

        return card

    @staticmethod
    def _read_plan_status(project_path: Path) -> tuple[str, str, str]:
        """Czyta status, aktualny task i numer sesji z PLAN.md. Zwraca (status, task, session)."""
        plan = project_path / "PLAN.md"
        if not plan.exists():
            return "", "", ""
        try:
            text = plan.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return "", "", ""

        status = ""
        task = ""
        session = ""
        in_meta = False
        for line in text.splitlines():
            s = line.strip()
            if s == "## Meta" or "<!-- SECTION:meta -->" in s:
                in_meta = True
            elif s.startswith("## ") and in_meta:
                in_meta = False
            if in_meta:
                if s.startswith("- status:"):
                    status = s.split(":", 1)[1].strip()
                elif s.startswith("- session:"):
                    session = s.split(":", 1)[1].strip()
            if s.startswith("- task:"):
                task = s.split(":", 1)[1].strip()

        return status, task, session

    @staticmethod
    def _read_ps_status(project_path: Path) -> tuple[str, str]:
        """Czyta status i wynik oceny z PS.md. Zwraca (status, score_summary)."""
        ps = project_path / "PS.md"
        if not ps.exists():
            return "brak", ""
        try:
            text = ps.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return "błąd", ""

        status = ""
        mean_competence = ""
        mean_arch = ""

        # status z sekcji meta
        in_meta = False
        for line in text.splitlines():
            s = line.strip()
            if "<!-- SECTION:meta -->" in s:
                in_meta = True
            elif "<!-- /SECTION:meta -->" in s:
                in_meta = False
            if in_meta and s.startswith("- status:"):
                status = s.split(":", 1)[1].strip()

        # mean ze score_competence i score_architecture
        for section_marker, store in [
            ("<!-- SECTION:score_competence -->", "comp"),
            ("<!-- SECTION:score_architecture -->", "arch"),
        ]:
            in_section = False
            in_aggregate = False
            for line in text.splitlines():
                s = line.strip()
                if section_marker in s:
                    in_section = True
                elif "<!-- /SECTION:" in s and in_section:
                    in_section = False
                if in_section and "### aggregate" in s:
                    in_aggregate = True
                elif in_section and s.startswith("### ") and in_aggregate:
                    in_aggregate = False
                if in_aggregate and s.startswith("- mean:"):
                    val = s.split(":", 1)[1].strip()
                    if val and val not in ("-", "—"):
                        if store == "comp":
                            mean_competence = val
                        else:
                            mean_arch = val

        score_parts = []
        if mean_competence:
            score_parts.append(f"comp {mean_competence}")
        if mean_arch:
            score_parts.append(f"arch {mean_arch}")
        score_summary = " · ".join(score_parts)

        return (status or "—"), score_summary

    def _count_cc_sessions(self, project_path: str) -> int | None:
        cc_dir = self._path_to_cc_project_dir(project_path)
        if not cc_dir:
            return None
        return len(list(cc_dir.glob("*.jsonl")))

    # -- Pomocnicze -------------------------------------------------------

    @staticmethod
    def _path_to_cc_project_dir(project_path: str) -> Path | None:
        """Konwertuje ścieżkę projektu na katalog w ~/.claude/projects/."""
        if not project_path:
            return None
        raw = str(Path(project_path))
        folder = re.sub(r'[^a-zA-Z0-9]', '-', raw)
        cc_dir = Path.home() / ".claude" / "projects" / folder
        return cc_dir if cc_dir.is_dir() else None

    def _latest_jsonl(self, project_path: str) -> Path | None:
        """Zwraca najnowszy plik .jsonl dla danego projektu."""
        cc_dir = self._path_to_cc_project_dir(project_path)
        if not cc_dir:
            return None
        files = sorted(cc_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0] if files else None

    def _on_jsonl_changed(self, path: str) -> None:
        if path not in self._jsonl_watcher.files():
            if Path(path).exists():
                self._jsonl_watcher.addPath(path)
        self.reload_jsonl_transcript()

    def _on_jsonl_dir_changed(self, _path: str) -> None:
        self.reload_jsonl_transcript()

    def _switch_logi_view(self, project_path: str) -> str | None:
        """Przełącza stack na właściwy widok i aktualizuje badge. Zwraca wersję SSS lub None."""
        sss_ver = self._detect_sss_version(project_path)
        if sss_ver:
            self._logi_stack.setCurrentIndex(self._LOGI_PAGE_SSS)
            self._logi_type_badge.setText(f"SSS {sss_ver}")
            self._logi_type_badge.setStyleSheet(
                f"background:{'#1a2a1a' if sss_ver == 'v3' else '#2a1a00'};"
                f"color:{'#98c379' if sss_ver == 'v3' else '#e5c07b'};"
                "border-radius:3px;padding:2px 8px;font-size:10px;font-weight:bold;"
            )
            self._logi_type_badge.setVisible(True)
            self._rebuild_sss_status_cards(project_path, sss_ver)
        else:
            self._logi_stack.setCurrentIndex(self._LOGI_PAGE_PLAIN)
            self._logi_type_badge.setText("non-SSS")
            self._logi_type_badge.setStyleSheet(
                "background:#252526;color:#5c6370;border-radius:3px;"
                "padding:2px 8px;font-size:10px;"
            )
            self._logi_type_badge.setVisible(True)
        return sss_ver

    def reload_jsonl_transcript(self) -> None:
        """Wczytuje najnowszy plik .jsonl CC i wyświetla transkrypt w aktywnym widoku."""
        project_path = self._path_edit.toPlainText().strip()
        sss_ver = self._switch_logi_view(project_path)

        # Który QTextEdit jest aktywny
        active_view: QTextEdit = (
            self._jsonl_view_sss if sss_ver else self._jsonl_view
        )

        latest = self._latest_jsonl(project_path)
        if latest is None:
            cc_dir = self._path_to_cc_project_dir(project_path)
            if cc_dir is None:
                msg = "(projekt nie ustawiony lub brak katalogu CC dla tej ścieżki)"
            else:
                msg = f"(brak plików .jsonl w {cc_dir})"
            active_view.setPlainText(msg)
            self._jsonl_file_lbl.setText("")
            if cc_dir and str(cc_dir) not in self._jsonl_watcher.directories():
                self._jsonl_watcher.addPath(str(cc_dir))
            return

        cc_dir = latest.parent
        if str(cc_dir) not in self._jsonl_watcher.directories():
            self._jsonl_watcher.addPath(str(cc_dir))
        if str(latest) not in self._jsonl_watcher.files():
            self._jsonl_watcher.addPath(str(latest))

        self._jsonl_file_lbl.setText(latest.name[:20] + "…")

        try:
            raw_lines = latest.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        except Exception as exc:
            active_view.setPlainText(f"(błąd odczytu: {exc})")
            return

        _COLOR_USER = QColor("#7dd3fc")
        _COLOR_ASST = QColor("#86efac")
        _COLOR_TS   = QColor("#6b7280")

        _fmt_user = QTextCharFormat()
        _fmt_user.setForeground(_COLOR_USER)
        _fmt_asst = QTextCharFormat()
        _fmt_asst.setForeground(_COLOR_ASST)
        _fmt_ts = QTextCharFormat()
        _fmt_ts.setForeground(_COLOR_TS)

        active_view.clear()
        cursor = active_view.textCursor()
        has_any = False

        for raw in raw_lines:
            try:
                d = json.loads(raw)
            except Exception:
                continue
            msg_type = d.get("type", "")
            ts = d.get("timestamp", "")
            short_ts = ts[11:19] if len(ts) >= 19 else ts

            if msg_type == "user":
                content = d.get("message", {}).get("content", "")
                if isinstance(content, list):
                    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    content = " ".join(parts)
                content = str(content).strip()
                if not content or content.startswith("<"):
                    continue
                text_body = content.replace("\n", " ")[:300]
                cursor.insertText(f"[{short_ts}] ", _fmt_ts)
                cursor.insertText(f"U: {text_body}\n", _fmt_user)
                has_any = True

            elif msg_type == "assistant":
                msg_obj = d.get("message", {})
                content_blocks = msg_obj.get("content", [])
                if isinstance(content_blocks, list):
                    texts = [b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
                    text = " ".join(texts).strip()
                elif isinstance(content_blocks, str):
                    text = content_blocks.strip()
                else:
                    text = ""
                if not text:
                    continue
                text_body = text.replace("\n", " ")[:300]
                cursor.insertText(f"[{short_ts}] ", _fmt_ts)
                cursor.insertText(f"A: {text_body}\n", _fmt_asst)
                has_any = True

        if not has_any:
            active_view.setPlainText("(plik nie zawiera wiadomości user/assistant)")
        else:
            active_view.moveCursor(QTextCursor.MoveOperation.End)

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

        # Splitter: lista sesji (lewa) | widok konwersacji (prawa)
        h_split = QSplitter(Qt.Orientation.Horizontal)

        # ── Lewa: lista sesji ──────────────────────────────────────────
        self._sesje_list = QListWidget()
        self._sesje_list.setMaximumWidth(190)
        self._sesje_list.setMinimumWidth(120)
        self._sesje_list.setFont(_FONT_SMALL)
        self._sesje_list.setStyleSheet(
            "QListWidget{"
            "background:#111111;border:none;"
            "border-right:1px solid #2a2a2a;"
            "}"
            "QListWidget::item{"
            "padding:5px 8px;"
            "color:#aaaaaa;"
            "border-bottom:1px solid #1e1e1e;"
            "}"
            "QListWidget::item:selected{"
            "background:#1e3a5f;color:#ffffff;"
            "}"
            "QListWidget::item:hover:!selected{"
            "background:#1a1a1a;"
            "}"
        )
        self._sesje_list.currentRowChanged.connect(self._on_sesje_selected)
        h_split.addWidget(self._sesje_list)

        # ── Prawa: widok konwersacji ───────────────────────────────────
        self._sesje_view = QTextEdit()
        self._sesje_view.setReadOnly(True)
        self._sesje_view.setFont(_FONT_MONO)
        self._sesje_view.setStyleSheet(
            "QTextEdit{background:#0d0d0d;color:#cccccc;border:none;padding:8px;}"
        )
        h_split.addWidget(self._sesje_view)
        h_split.setSizes([160, 600])
        lay.addWidget(h_split, stretch=1)

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
        """Wczytuje listę wszystkich transkryptów projektu; ładuje najnowszy."""
        project_path = self._path_edit.toPlainText().strip()
        self._sesje_list.blockSignals(True)
        self._sesje_list.clear()
        self._sesje_transcripts = []

        if not project_path:
            self._sesje_list.blockSignals(False)
            self._sesje_view.setHtml(
                "<p style='color:#5c6370;margin:16px;'>Brak ścieżki projektu.</p>"
            )
            self._lbl_sesje_path.setText("")
            self._lbl_cc_sessions.setText("")
            self._lbl_cc_last.setText("")
            return

        entries = list_project_transcripts(project_path)
        self._sesje_transcripts = entries

        for path, mtime, size in entries:
            dt = datetime.fromtimestamp(mtime)
            label = dt.strftime("%Y-%m-%d\n%H:%M:%S")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            kb = size // 1024
            item.setToolTip(f"{path.name}\n{kb} KB")
            self._sesje_list.addItem(item)

        count = len(entries)
        self._lbl_cc_sessions.setText(f"{count} sesji CC")
        self._sesje_list.blockSignals(False)

        if entries:
            self._sesje_list.setCurrentRow(0)
        else:
            self._sesje_view.setHtml(
                "<p style='color:#5c6370;margin:16px;'>"
                "Brak transkryptów w ~/.claude/projects/ dla tego projektu.</p>"
            )
            self._lbl_sesje_path.setText("(brak transkryptów)")
            self._lbl_cc_last.setText("")

    def _on_sesje_selected(self, row: int) -> None:
        """Ładuje wybrany transkrypt do widoku konwersacji."""
        if row < 0 or row >= len(self._sesje_transcripts):
            return
        path, mtime, _ = self._sesje_transcripts[row]
        self._lbl_sesje_path.setText(path.name)
        self._lbl_cc_last.setText(datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"))
        messages = read_transcript_messages(path)
        if not messages:
            self._sesje_view.setHtml(
                "<p style='color:#5c6370;margin:16px;'>Brak wiadomości w transkrypcie.</p>"
            )
            return
        self._sesje_view.setHtml(_render_conversation_html(messages))
        # Przewiń do końca (najnowsze wiadomości)
        self._sesje_view.moveCursor(QTextCursor.MoveOperation.End)

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

    # ---- Historia (dawna zakładka Sesje) ------------------------------- #

    def _build_historia_sesje_vibe(self) -> QWidget:
        # Tworzymy _transcript jako ukryty widget — nadal używany przez _last_msg
        self._transcript = QPlainTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setFont(_FONT_MONO)
        self._last_msg = self._transcript

        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sesje())
        return w

    # ---- Full Converter (SSC) ------------------------------------------ #

    def _build_full_converter(self) -> QWidget:
        if not _SSC_AVAILABLE or _SscView is None:
            w = QWidget()
            lay = QVBoxLayout(w)
            lbl = QLabel("Moduł SSC (Converter) niedostępny.")
            lbl.setStyleSheet("color:#5c6370;font-size:11px;")
            lay.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            return w
        self._ssc_widget = _SscView()
        return self._ssc_widget

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

        row.addWidget(self._btn_launch, stretch=2)
        return w

    # ------------------------------------------------------------------ #
    # Sygnały                                                               #
    # ------------------------------------------------------------------ #

    _TAB_PROMPT_SCORE = 9   # indeks zakładki Prompt Score w self._tabs (zewnętrzny)
    _TAB_EXPLORER    = 10
    _TAB_README      = 11
    _TAB_CHANGELOG   = 12

    def _connect_signals(self) -> None:
        self._btn_launch.clicked.connect(lambda: self.launch_requested.emit(self._slot_id))
        self._btn_browse.clicked.connect(self._on_browse)
        self._btn_plan_refresh.clicked.connect(self.reload_plan)
        self._btn_plan_save.clicked.connect(self._on_plan_save)
        self._btn_stats_refresh.clicked.connect(self.reload_stats)
        self._btn_sesje_refresh.clicked.connect(self._reload_sesje_view)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._pre_cmd_edit.textChanged,
            self._cc_flags_edit.textChanged,
            self._vibe_edit.textChanged,
            self._chk_verbose.stateChanged,
            self._chk_no_update.stateChanged,
        ):
            sig.connect(self._on_config_changed)
        self._session_mode_group.idToggled.connect(lambda _id, _checked: self._on_config_changed())
        self._plan_editor.textChanged.connect(lambda: self._btn_plan_save.setEnabled(True))

    def _on_tab_changed(self, index: int) -> None:
        if index == self._TAB_PROMPT_SCORE and not self._prompt_score_loaded:
            self._prompt_score_loaded = True
            self.reload_prompt_score()

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
        flags_parts: list[str] = []
        session_flags = ["", "--resume", "--continue"]
        sid = self._session_mode_group.checkedId()
        if sid > 0:
            flags_parts.append(session_flags[sid])
        if self._chk_verbose.isChecked():
            flags_parts.append("--verbose")
        if self._chk_no_update.isChecked():
            flags_parts.append("--no-update-check")
        if self._chk_no_flicker.isChecked():
            flags_parts.append("--no-flicker")
        extra = self._cc_flags_edit.toPlainText().strip()
        if extra:
            flags_parts.append(extra)
        raw_prompt = self._vibe_edit.toPlainText() or DEFAULT_VIBE_PROMPT
        if self._chk_focus.isChecked() and not raw_prompt.startswith("/focus"):
            vibe = "/focus\n" + raw_prompt
        elif not self._chk_focus.isChecked() and raw_prompt.startswith("/focus\n"):
            vibe = raw_prompt[len("/focus\n"):]
        else:
            vibe = raw_prompt
        return SlotConfig(
            project_path=self._path_edit.toPlainText().strip(),
            model=self._model_combo.currentText(),
            effort=self._effort_combo.currentText(),
            permission_mode=self._perm_combo.currentText(),
            pre_command=self._pre_cmd_edit.toPlainText().strip(),
            cc_flags=" ".join(flags_parts),
            vibe_prompt=vibe,
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

    def reload_prompt_score(self) -> None:
        path = self._path_edit.toPlainText().strip()
        if path:
            self._prompt_score.load_from_project(path, silent=True)

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
        """Odświeża zakładki CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md oraz Explorer/README/CHANGELOG."""
        for filename in ("CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md"):
            self._reload_md_file(filename)
        path_str = self._path_edit.toPlainText().strip()
        if path_str:
            p = Path(path_str)
            if p.is_dir():
                self._explorer_section.set_project(p)
                self._readme_section.set_project(p)
                self._changelog_section.set_project(p)

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
            self._pre_cmd_edit.textChanged,
            self._cc_flags_edit.textChanged,
            self._vibe_edit.textChanged,
            self._chk_verbose.stateChanged,
            self._chk_no_update.stateChanged,
        ):
            sig.disconnect(self._on_config_changed)
        self._session_mode_group.idToggled.disconnect()

        self._path_edit.setPlainText(self._config.project_path)
        idx = self._model_combo.findText(self._config.model)
        self._model_combo.setCurrentIndex(max(0, idx))
        idx = self._effort_combo.findText(self._config.effort)
        self._effort_combo.setCurrentIndex(max(0, idx))
        idx = self._perm_combo.findText(self._config.permission_mode)
        self._perm_combo.setCurrentIndex(max(0, idx))
        self._pre_cmd_edit.setPlainText(self._config.pre_command)
        self._vibe_edit.setPlainText(self._config.vibe_prompt)

        # Odtwórz stan widgetów flag z zapisanego cc_flags string
        saved_flags = getattr(self._config, "cc_flags", "")
        self._chk_verbose.setChecked("--verbose" in saved_flags)
        self._chk_no_update.setChecked("--no-update-check" in saved_flags)
        self._chk_no_flicker.setChecked("--no-flicker" in saved_flags)
        if "--resume" in saved_flags:
            self._session_mode_group.button(1).setChecked(True)
        elif "--continue" in saved_flags:
            self._session_mode_group.button(2).setChecked(True)
        else:
            self._session_mode_group.button(0).setChecked(True)
        # Odtwórz /focus z vibe_prompt
        saved_prompt = self._config.vibe_prompt
        self._chk_focus.setChecked(saved_prompt.startswith("/focus"))
        # W ręcznym polu zostawiamy tylko flagi spoza znanych
        _known = {"--resume", "--continue", "--verbose", "--no-update-check", "--no-flicker"}
        extra_flags = " ".join(
            t for t in saved_flags.split() if t not in _known
        )
        self._cc_flags_edit.setPlainText(extra_flags)

        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._pre_cmd_edit.textChanged,
            self._cc_flags_edit.textChanged,
            self._vibe_edit.textChanged,
            self._chk_verbose.stateChanged,
            self._chk_no_update.stateChanged,
        ):
            sig.connect(self._on_config_changed)
        self._session_mode_group.idToggled.connect(lambda _id, _checked: self._on_config_changed())

        if self._config.project_path:
            self._lbl_plan_path.setText(
                str(Path(self._config.project_path) / "PLAN.md")
            )
            self.reload_plan()
            self.reload_pcc()
            self.reload_stats()
            self.reload_history()
            self.reload_md_files()
            self.reload_jsonl_transcript()
            self._clean_clear.load_project(self._config.project_path)

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

    def _notify_sss(self, path: str) -> None:
        """Wykrywa projekt SSS (v2/v3) i emituje sss_detected; odświeża widok Logi."""
        sss_ver = self._detect_sss_version(path) if path else None
        is_sss = sss_ver is not None

        # Zachowaj kompatybilność: dla v2 czytaj project_name z intake.json
        if sss_ver == "v2":
            intake = _read_intake(path)
            name = (intake.get("project_name") or "") if intake else ""
        elif sss_ver == "v3":
            # Nazwa z PLAN.md (pierwsza linia) lub nazwa katalogu
            try:
                first_line = (Path(path) / "PLAN.md").read_text(encoding="utf-8").splitlines()[0]
                name = first_line.lstrip("#").strip() or Path(path).name
            except Exception:
                name = Path(path).name
        else:
            name = ""

        self._is_sss = is_sss
        self._sss_name = name
        self.sss_detected.emit(self._slot_id, is_sss, name)

        # Odśwież widok Logi (przełącza stronę stosu + karty statusu)
        self._switch_logi_view(path)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Wybierz katalog projektu",
            self._path_edit.toPlainText().strip() or str(Path.home()),
        )
        if folder:
            self._prompt_score_loaded = False
            self._path_edit.setPlainText(folder)
            self.reload_plan()
            self.reload_pcc()
            self.reload_stats()
            self.reload_history()
            self.reload_md_files()
            self._clean_clear.load_project(folder)
            self.reload_jsonl_transcript()
            if self._tabs.currentIndex() == self._TAB_PROMPT_SCORE:
                self._prompt_score_loaded = True
                self.reload_prompt_score()
            self._notify_sss(folder)

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

    def _render_history(self) -> None:
        self._reload_sesje_view()


    def stop_with_round_end(self) -> None:
        """Uruchamia round_end, po zakonczeniu terminuje sesje CC."""
        path = self._path_edit.toPlainText().strip()
        if not path:
            terminate_vscode_session(self._slot_id)
            self.stop_completed.emit(self._slot_id)
            return
        self._stop_pending = True
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
        self._workflow.run_git_push(path)

    def _show_git_init_dialog(self, path: str, then_round_end: bool = False) -> None:
        dlg = GitInitDialog(path, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
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
            self._workflow.run_round_end(path)

    def _on_workflow_done(self, name: str, ok: bool, msg: str) -> None:
        if name in ("round_end", "clean_plan") and ok:
            self.reload_plan()
            self.reload_pcc()
        if name == "git_init" and ok:
            self.reload_stats()
            if self._git_init_then_round_end:
                self._git_init_then_round_end = False
                path = self._path_edit.toPlainText().strip()
                if path:
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
    Na Windows pliki .cmd/.bat wymagają pośrednictwa cmd.exe.
    """
    import sys as _sys
    cc_args = ["--print", "--output-format", "stream-json", "--verbose"]
    if _sys.platform == "win32" and cc.lower().endswith((".cmd", ".bat")):
        # QProcess nie może bezpośrednio uruchomić .cmd — potrzebuje cmd.exe.
        # cmd /c traktuje cały string jako jedną komendę — ścieżka BEZ cudzysłowów wewnętrznych.
        args_str = " ".join(cc_args)
        proc.setProgram("cmd")
        proc.setArguments(["/c", f'{cc} {args_str}'])
    else:
        proc.setProgram(cc)
        proc.setArguments(cc_args)
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

    Dwukrotne kliknięcie prawym klawiszem na zakładce emituje folder_change_requested(index).
    """

    folder_change_requested = Signal(int)

    def __init__(self, colors: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors = [QColor(c) for c in colors]
        n = len(colors)
        self._sub_labels: list[str] = [""] * n
        self._status_labels: list[tuple[str, QColor]] = [
            ("", _STATUS_COLOR_OFFLINE) for _ in range(n)
        ]
        self._hover_index = -1
        self._sss_flags: list[bool] = [False] * n
        self._sss_plan_texts: list[str] = [""] * n
        self.setMouseTracking(True)
        self.setExpanding(False)
        self.setDrawBase(False)

    def setSubLabel(self, index: int, text: str) -> None:
        if 0 <= index < len(self._sub_labels):
            self._sub_labels[index] = text or ""
            self.update()

    def setSssFlag(self, index: int, is_sss: bool) -> None:
        if 0 <= index < 4:
            self._sss_flags[index] = is_sss
            self.update()

    def setSssPlanText(self, index: int, text: str) -> None:
        if 0 <= index < 4:
            self._sss_plan_texts[index] = text
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

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.RightButton:
            try:
                point = event.position().toPoint()
            except AttributeError:
                point = event.pos()
            idx = self.tabAt(point)
            if idx >= 0:
                self.folder_change_requested.emit(idx)
            return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for i in range(self.count()):
            color = self._colors[i] if i < len(self._colors) else QColor("#888888")
            rect = self.tabRect(i)
            is_selected = (i == self.currentIndex())
            is_hover = (i == self._hover_index)

            # ── Tło karty ─────────────────────────────────────────────────
            if is_selected:
                bg = QColor("#242424")
            elif is_hover:
                bg = QColor("#1e1e1e")
            else:
                bg = QColor("#181818")
            painter.fillRect(rect, bg)

            # ── Lewy pasek akcentu (4 px) ─────────────────────────────────
            accent = QColor(color)
            if not is_selected:
                accent.setAlpha(130)
            painter.fillRect(QRect(rect.x(), rect.y(), 4, rect.height()), accent)

            # ── Dolna linia dla wybranej zakładki ─────────────────────────
            if is_selected:
                painter.fillRect(
                    QRect(rect.x(), rect.bottom() - 2, rect.width(), 2),
                    QColor(color),
                )

            # ── Dane ──────────────────────────────────────────────────────
            sub_text = self._sub_labels[i] if i < len(self._sub_labels) else ""
            status_text, status_color = (
                self._status_labels[i] if i < len(self._status_labels)
                else ("", _STATUS_COLOR_OFFLINE)
            )
            is_sss = self._sss_flags[i] if i < len(self._sss_flags) else False
            sss_plan_text = self._sss_plan_texts[i] if i < len(self._sss_plan_texts) else ""

            h = rect.height()
            cx = rect.x() + 8       # x startu tekstu (po pasku 4px + padding 4px)
            cw = rect.width() - 12  # szerokość obszaru tekstu

            # ── Mała flaga z numerem slotu (top-right) ────────────────────
            flag_w, flag_h = 18, 14
            flag_rect = QRect(rect.right() - flag_w - 3, rect.y() + 4, flag_w, flag_h)
            flag_bg = QColor(color)
            flag_bg.setAlpha(200 if is_selected else 110)
            painter.fillRect(flag_rect, flag_bg)
            ff = QFont("Segoe UI", 7)
            ff.setBold(True)
            painter.setFont(ff)
            painter.setPen(QColor("#000000") if is_selected else QColor(color).lighter(160))
            painter.drawText(flag_rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))

            # ── Badge SSS (obok flagi) ────────────────────────────────────
            if is_sss:
                sss_rect = QRect(rect.right() - flag_w - 34, rect.y() + 4, 28, flag_h)
                painter.fillRect(sss_rect, QColor("#7c3aed"))
                fb = QFont("Segoe UI", 7)
                fb.setBold(True)
                painter.setFont(fb)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(sss_rect, Qt.AlignmentFlag.AlignCenter, "SSS")

            # ── Nazwa projektu (duża, zajmuje górne ~2/3) ─────────────────
            name_area_h = h - 22  # zostaw 22px na status
            name_rect = QRect(cx, rect.y() + 4, cw - flag_w - 6, name_area_h - 4)
            fn = QFont("Segoe UI", 12)
            fn.setBold(True)
            painter.setFont(fn)
            name_color = QColor(color) if is_selected else QColor(color).darker(115)
            painter.setPen(name_color)
            if sub_text:
                metrics = painter.fontMetrics()
                elided = metrics.elidedText(sub_text, Qt.TextElideMode.ElideMiddle, cw - flag_w - 8)
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
            else:
                painter.setPen(QColor("#2e2e2e"))
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "—")

            # ── Status CC lub PLAN.md SSS (dolny pasek 20px) ─────────────
            r3 = QRect(cx, rect.bottom() - 20, cw, 18)
            cc_offline = not status_text or "brak sesji" in status_text

            if is_sss and sss_plan_text and cc_offline:
                plan_bg = QColor("#4c1d95")
                plan_bg.setAlpha(80 if is_selected else 50)
                painter.fillRect(QRect(rect.x() + 4, r3.y(), rect.width() - 4, r3.height()), plan_bg)
                fs = QFont("Segoe UI", 8)
                painter.setFont(fs)
                painter.setPen(QColor("#c4b5fd"))
                metrics = painter.fontMetrics()
                elided = metrics.elidedText(sss_plan_text, Qt.TextElideMode.ElideRight, cw)
                painter.drawText(r3, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
            else:
                fs = QFont("Segoe UI", 8)
                painter.setFont(fs)
                if cc_offline:
                    painter.setPen(QColor("#333333"))
                elif "working" in status_text:
                    painter.setPen(QColor(_STATUS_COLOR_WORKING))
                else:
                    painter.setPen(QColor(_STATUS_COLOR_WAITING))
                if status_text:
                    metrics = painter.fontMetrics()
                    elided = metrics.elidedText(status_text, Qt.TextElideMode.ElideRight, cw)
                    painter.drawText(r3, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)


def _render_conversation_html(messages: list[dict]) -> str:
    """Renderuje listę wiadomości {type, text} jako HTML do QTextEdit."""
    import html as _html

    parts = [
        "<html><body style='background:#0d0d0d;margin:0;padding:0;"
        "font-family:Consolas,monospace;font-size:13px;'>"
    ]
    for msg in messages:
        role = msg.get("type", "")
        text = _html.escape(msg.get("text", "").strip())
        text = text.replace("\n", "<br>")

        if role == "user":
            parts.append(
                f"<div style='"
                f"background:#0e1e2e;"
                f"border-left:3px solid #569cd6;"
                f"margin:6px 8px 2px 8px;"
                f"padding:6px 10px;"
                f"border-radius:0 4px 4px 0;'>"
                f"<span style='color:#b0c8e0;'>{text}</span>"
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
                f"<span style='color:#c8e0c8;'>{text}</span>"
                f"</div>"
            )

    parts.append("</body></html>")
    return "".join(parts)


# ─── Discovery Panel ──────────────────────────────────────────────────────────

class _DiscoveryCard(QFrame):
    """Karta jednej wykrytej sesji CC (psutil).

    Dwa tryby wizualne:
    - zarządzana (assigned_slot > 0): kolorowa ramka po lewej + badge slotu, brak przycisków promote
    - wolna (assigned_slot = 0): ciemna ramka, przyciski → Slot N
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Kolorowy pasek po lewej (widoczny tylko dla zarządzanych)
        self._accent_bar = QFrame()
        self._accent_bar.setFixedWidth(4)
        self._accent_bar.setStyleSheet("background:#333333;border:none;border-radius:0;")
        outer.addWidget(self._accent_bar)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        root = QVBoxLayout(inner)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(2)
        outer.addWidget(inner, stretch=1)

        # Wiersz nagłówkowy: nazwa + badge slotu
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.setSpacing(4)

        self._name_lbl = QLabel()
        self._name_lbl.setStyleSheet("color:#c8c8c8;font-size:11px;font-weight:bold;border:none;")
        hdr_row.addWidget(self._name_lbl, stretch=1)

        self._slot_badge = QLabel()
        self._slot_badge.setFixedHeight(16)
        self._slot_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._slot_badge.setStyleSheet(
            "color:#000;font-size:8px;font-weight:bold;border-radius:3px;"
            "padding:0 5px;border:none;"
        )
        self._slot_badge.hide()
        hdr_row.addWidget(self._slot_badge)
        root.addLayout(hdr_row)

        self._path_lbl = QLabel()
        self._path_lbl.setStyleSheet("color:#484848;font-size:8px;border:none;")
        root.addWidget(self._path_lbl)

        self._meta_lbl = QLabel()
        self._meta_lbl.setStyleSheet("color:#585858;font-size:8px;border:none;")
        root.addWidget(self._meta_lbl)

        self._btn_row = QWidget()
        self._btn_row.setStyleSheet("background:transparent;border:none;")
        self._btn_layout = QHBoxLayout(self._btn_row)
        self._btn_layout.setContentsMargins(0, 3, 0, 0)
        self._btn_layout.setSpacing(4)
        self._btn_layout.addStretch()
        root.addWidget(self._btn_row)

    def update_session(
        self,
        session: object,
        free_slots: list[int],
        on_promote,
        assigned_slot: int = 0,
    ) -> None:
        cwd: str = getattr(session, "cwd", "")
        self._name_lbl.setText(getattr(session, "project_name", "?"))

        short_path = ("…" + cwd[-26:]) if len(cwd) > 28 else cwd
        self._path_lbl.setText(short_path)
        self._path_lbl.setToolTip(cwd)

        elapsed = getattr(session, "elapsed_seconds", 0)
        mins, secs = divmod(elapsed, 60)
        hrs, mins = divmod(mins, 60)
        elapsed_str = f"{hrs}h {mins}m" if hrs else (f"{mins}m {secs:02d}s" if mins else f"{secs}s")
        pid = getattr(session, "pid", "?")
        self._meta_lbl.setText(f"PID:{pid}  {elapsed_str}")

        if assigned_slot:
            # ── Karta zarządzana ─────────────────────────────────────────
            color = SLOT_COLORS[assigned_slot - 1]
            self.setStyleSheet(
                f"QFrame{{background:#161616;border:1px solid {color}44;"
                f"border-left:none;border-radius:0 4px 4px 0;}}"
            )
            self._accent_bar.setStyleSheet(
                f"background:{color};border:none;border-radius:0;"
            )
            self._name_lbl.setStyleSheet(
                f"color:{color};font-size:11px;font-weight:bold;border:none;"
            )
            self._slot_badge.setText(f"Slot {assigned_slot}")
            self._slot_badge.setStyleSheet(
                f"background:{color};color:#000;font-size:8px;"
                f"font-weight:bold;border-radius:3px;padding:0 5px;border:none;"
            )
            self._slot_badge.show()
            self._btn_row.hide()
        else:
            # ── Karta wolna ──────────────────────────────────────────────
            self.setStyleSheet(
                "QFrame{background:#1a1a1a;border:1px solid #2e2e2e;"
                "border-left:none;border-radius:0 4px 4px 0;}"
            )
            self._accent_bar.setStyleSheet("background:#2e2e2e;border:none;border-radius:0;")
            self._name_lbl.setStyleSheet(
                "color:#c8c8c8;font-size:11px;font-weight:bold;border:none;"
            )
            self._slot_badge.hide()
            self._btn_row.show()

            # Przebuduj przyciski promote
            while self._btn_layout.count() > 1:
                item = self._btn_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if free_slots:
                for slot_id in free_slots[:3]:
                    btn = QPushButton(f"→ {slot_id}")
                    btn.setFixedHeight(18)
                    btn.setToolTip(f"Przypisz do Slotu {slot_id}")
                    btn.setStyleSheet(
                        "QPushButton{background:#1e2e1e;color:#6ec87e;"
                        "border:1px solid #2e4a2e;border-radius:3px;"
                        "padding:0 6px;font-size:9px;}"
                        "QPushButton:hover{background:#2a3e2a;}"
                    )
                    btn.clicked.connect(
                        lambda checked, s=slot_id, c=cwd: on_promote(c, s)
                    )
                    self._btn_layout.insertWidget(self._btn_layout.count() - 1, btn)
            else:
                lbl = QLabel("brak wolnych slotów")
                lbl.setStyleSheet("color:#484848;font-size:8px;border:none;")
                self._btn_layout.insertWidget(0, lbl)


def _read_cwd_from_jsonl(project_dir: Path) -> str:
    """Odczytuje CWD z pierwszego pliku JSONL w katalogu projektu CC."""
    try:
        files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return ""
        # Szukaj w pierwszych 20 liniach pliku — szukamy pola cwd w wiadomości user
        for line in files[0].read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
            try:
                d = json.loads(line)
                cwd = d.get("cwd", "")
                if cwd:
                    return cwd
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _scan_recent_cc_projects(max_count: int = 20) -> list[tuple[str, str, float]]:
    """Skanuje ~/.claude/projects/ i zwraca listę (display_name, cwd_path, mtime).

    Sortuje od najnowszego. Projekty bez rozpoznanego CWD są pomijane.
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.is_dir():
        return []

    dirs: list[tuple[float, Path]] = []
    try:
        for d in projects_dir.iterdir():
            if d.is_dir():
                try:
                    dirs.append((d.stat().st_mtime, d))
                except OSError:
                    pass
    except OSError:
        return []

    dirs.sort(reverse=True)

    results: list[tuple[str, str, float]] = []
    for mtime, d in dirs:
        if len(results) >= max_count:
            break
        cwd = _read_cwd_from_jsonl(d)
        if not cwd:
            continue
        display = Path(cwd).name or d.name
        results.append((display, cwd, mtime))

    return results


class _CompactItemDelegate(QStyledItemDelegate):
    """Wymusza stałą wysokość wiersza niezależnie od paddingu Qt."""
    _ROW_H = 14

    def sizeHint(self, option, index):  # type: ignore[override]
        sh = super().sizeHint(option, index)
        return sh.__class__(sh.width(), self._ROW_H)


class _RecentProjectList(QWidget):
    """Lista ostatnich 20 projektów CC z obsługą LMB → slot5, RMB → slot6."""

    project_lmb = Signal(str)   # path
    project_rmb = Signal(str)   # path

    _COLOR_L = "#8b8fa8"   # kolor slotu 5
    _COLOR_R = "#6e7288"   # kolor slotu 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paths: list[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 2, 4)
        lay.setSpacing(3)

        hdr_row = QHBoxLayout()
        hdr = QLabel("Ostatnie projekty CC")
        hdr.setStyleSheet(
            "color:#484848;font-size:9px;font-weight:bold;"
            "letter-spacing:1px;background:transparent;"
        )
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedSize(18, 18)
        btn_refresh.setStyleSheet(
            "QPushButton{background:transparent;color:#484848;border:none;font-size:10px;}"
            "QPushButton:hover{color:#888888;}"
        )
        btn_refresh.clicked.connect(self.refresh)
        hdr_row.addWidget(btn_refresh)
        lay.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#242424;background:#242424;")
        sep.setFixedHeight(1)
        lay.addWidget(sep)

        # Legenda LMB/RMB
        legend = QHBoxLayout()
        for label, color in [("L", self._COLOR_L), ("P", self._COLOR_R)]:
            lbl = QLabel(f"● {label}")
            lbl.setStyleSheet(
                f"color:{color};font-size:8px;background:transparent;"
            )
            legend.addWidget(lbl)
        legend.addStretch()
        hint = QLabel("LMB / PPM")
        hint.setStyleSheet("color:#303030;font-size:8px;background:transparent;")
        legend.addWidget(hint)
        lay.addLayout(legend)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item{color:#5c6370;font-size:8px;padding:0px 4px;}"
            "QListWidget::item:hover{background:#1e1e1e;color:#9d9d9d;}"
            "QListWidget::item:selected{background:#252525;color:#cccccc;}"
        )
        self._list.setUniformItemSizes(True)
        self._list.setItemDelegate(_CompactItemDelegate(self._list))
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.verticalScrollBar().setStyleSheet(
            "QScrollBar:vertical{background:#1a1a1a;width:5px;border:none;}"
            "QScrollBar::handle:vertical{background:#333333;border-radius:2px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_rmb)
        self._list.itemClicked.connect(self._on_lmb)
        lay.addWidget(self._list, stretch=1)

        # Pasek wskazówki na dole
        tip = QLabel("LMB → Podgląd L   PPM → Podgląd P")
        tip.setStyleSheet("color:#2a2a2a;font-size:8px;background:transparent;")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(tip)

    def refresh(self) -> None:
        projects = _scan_recent_cc_projects(20)
        self._paths = []
        self._list.clear()
        for display, cwd, _mtime in projects:
            self._paths.append(cwd)
            item = QListWidgetItem()
            item.setText(display)
            item.setToolTip(cwd)
            self._list.addItem(item)

    def _on_lmb(self, item: QListWidgetItem) -> None:
        idx = self._list.row(item)
        if 0 <= idx < len(self._paths) and self._paths[idx]:
            self.project_lmb.emit(self._paths[idx])

    def _on_rmb(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        idx = self._list.row(item)
        if 0 <= idx < len(self._paths) and self._paths[idx]:
            self.project_rmb.emit(self._paths[idx])


class _DiscoveryPanel(QWidget):
    """Prawostronny panel:
    - górna połowa: aktywne sesje CC (psutil-based)
    - dolna połowa: lista 20 ostatnich projektów CC (LMB → slot5, RMB → slot6)

    Sesje przypisane do slotów 1–4 są wyróżnione kolorem slotu.
    Sesje wolne mają przyciski promote → Slot N.
    """

    project_lmb = Signal(str)
    project_rmb = Signal(str)

    def __init__(
        self,
        get_free_slots,
        on_promote,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_free_slots = get_free_slots
        self._on_promote = on_promote
        self._cards: list[_DiscoveryCard] = []
        self._setup_ui()
        self.setFixedWidth(205)
        self.setStyleSheet("background:#111111;")

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1e1e1e;}"
            "QSplitter::handle:hover{background:#2a2a2a;}"
        )

        # ── Górna część: aktywne sesje ──────────────────────────────────
        top_w = QWidget()
        top_w.setStyleSheet("background:transparent;")
        top_lay = QVBoxLayout(top_w)
        top_lay.setContentsMargins(6, 6, 2, 4)
        top_lay.setSpacing(4)

        hdr = QLabel("Aktywne sesje CC")
        hdr.setStyleSheet(
            "color:#484848;font-size:9px;font-weight:bold;"
            "letter-spacing:1px;background:transparent;"
        )
        top_lay.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#242424;background:#242424;")
        sep.setFixedHeight(1)
        top_lay.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:#1a1a1a;width:5px;border:none;}"
            "QScrollBar::handle:vertical{background:#333333;border-radius:2px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        cards_container = QWidget()
        cards_container.setStyleSheet("background:transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 4, 0)
        cards_layout.setSpacing(5)

        for _ in range(8):
            card = _DiscoveryCard(cards_container)
            card.hide()
            self._cards.append(card)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_container)
        top_lay.addWidget(scroll, stretch=1)

        self._empty_lbl = QLabel("Brak aktywnych\nsesji CC")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            "color:#303030;font-size:10px;background:transparent;"
        )
        top_lay.addWidget(self._empty_lbl)

        self._no_psutil_lbl = QLabel("Zainstaluj psutil:\npip install psutil")
        self._no_psutil_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_psutil_lbl.setStyleSheet(
            "color:#553333;font-size:9px;background:transparent;"
        )
        self._no_psutil_lbl.hide()
        top_lay.addWidget(self._no_psutil_lbl)

        splitter.addWidget(top_w)

        # ── Dolna część: ostatnie projekty ──────────────────────────────
        self._recent = _RecentProjectList()
        self._recent.project_lmb.connect(self.project_lmb)
        self._recent.project_rmb.connect(self.project_rmb)
        splitter.addWidget(self._recent)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

        # Wstępne załadowanie listy
        QTimer.singleShot(800, self._recent.refresh)

    def refresh(self, sessions: list, slot_assignment: dict) -> None:
        """Odświeża karty dla wszystkich sesji."""
        try:
            import psutil  # noqa: F401
            psutil_ok = True
        except ImportError:
            psutil_ok = False

        if not psutil_ok:
            self._no_psutil_lbl.show()
            self._empty_lbl.hide()
            for card in self._cards:
                card.hide()
            return

        self._no_psutil_lbl.hide()
        free_slots = self._get_free_slots()

        from src.watchers.process_scanner import norm_path as _np
        for i, card in enumerate(self._cards):
            if i < len(sessions):
                sess = sessions[i]
                assigned = slot_assignment.get(_np(getattr(sess, "cwd", "")), 0)
                card.update_session(sess, free_slots, self._on_promote, assigned_slot=assigned)
                card.show()
            else:
                card.hide()
        self._empty_lbl.setVisible(len(sessions) == 0)

    def refresh_recent(self) -> None:
        """Odświeża listę ostatnich projektów."""
        self._recent.refresh()


# ──────────────────────────────────────────────────────────────────────────────

class _MonitorView(QWidget):
    """Widok Monitor — lista slotów po lewej, szczegóły po prawej."""

    # kolory faz
    _PHASE_COLOR = {"working": "#f9c74f", "waiting": "#a6e3a1"}
    _STATUS_ICON = {"distributed": "✓", "in_plan": "●"}
    _STATUS_COLOR = {"distributed": "#6c7086", "in_plan": "#cdd6f4"}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_idx: int = 0       # wybrany slot (0-based)
        self._slots_data: list[dict] = []  # cache ostatnich danych
        self._build_ui()

    # ── Budowanie UI ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Lewa: lista slotów ────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(170)
        left.setStyleSheet("background:#13131e;border-right:1px solid #2a2a3a;")
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 6, 0, 6)
        llay.setSpacing(2)

        self._slot_btns: list[QPushButton] = []
        for i in range(len(SLOT_COLORS)):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(SLOT_COLORS[i], checked=False))
            btn.clicked.connect(lambda _c, idx=i: self._select(idx))
            btn.setMinimumHeight(52)
            btn.setMaximumHeight(68)
            self._slot_btns.append(btn)
            llay.addWidget(btn)

        llay.addStretch()
        root.addWidget(left)

        # ── Prawa: szczegóły ──────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background:#181825;")
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(14, 12, 14, 12)
        rlay.setSpacing(6)

        # nagłówek szczegółów
        hdr = QHBoxLayout()
        self._det_name = QLabel("—", styleSheet="color:#cdd6f4;font-size:13px;font-weight:bold;")
        self._det_badge = QLabel("", styleSheet=(
            "color:#cba6f7;font-size:9px;font-weight:bold;"
            "background:#2a2040;border-radius:3px;padding:1px 5px;"
        ))
        self._det_phase = QLabel("", styleSheet="color:#585b70;font-size:10px;")
        hdr.addWidget(self._det_name, stretch=1)
        hdr.addWidget(self._det_badge)
        hdr.addWidget(self._det_phase)
        rlay.addLayout(hdr)

        self._det_path = QLabel("", styleSheet="color:#3a3a5a;font-size:9px;")
        self._det_path.setWordWrap(True)
        rlay.addWidget(self._det_path)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame{color:#2a2a3a;margin:2px 0;}")
        rlay.addWidget(sep)

        # ── Stack: SSS / Plain / Pusty ────────────────────────────────
        self._stack = QStackedWidget()

        # strona 0 — SSS
        sss_page = QWidget()
        sss_lay = QVBoxLayout(sss_page)
        sss_lay.setContentsMargins(0, 0, 0, 0)
        sss_lay.setSpacing(6)

        # meta SSS
        self._sss_meta = QLabel("", styleSheet="color:#89b4fa;font-size:10px;")
        sss_lay.addWidget(self._sss_meta)

        # nagłówek bufora
        buf_hdr = QLabel("BUFOR", styleSheet=(
            "color:#6c7086;font-size:9px;font-weight:bold;letter-spacing:1px;"
        ))
        sss_lay.addWidget(buf_hdr)

        # lista wpisów bufora (scrollowalny obszar)
        buf_scroll = QScrollArea()
        buf_scroll.setWidgetResizable(True)
        buf_scroll.setFrameShape(QFrame.Shape.NoFrame)
        buf_scroll.setStyleSheet("background:transparent;")
        self._buf_widget = QWidget()
        self._buf_widget.setStyleSheet("background:transparent;")
        self._buf_layout = QVBoxLayout(self._buf_widget)
        self._buf_layout.setContentsMargins(0, 0, 0, 0)
        self._buf_layout.setSpacing(3)
        self._buf_layout.addStretch()
        buf_scroll.setWidget(self._buf_widget)
        sss_lay.addWidget(buf_scroll, stretch=1)
        self._stack.addWidget(sss_page)    # idx 0

        # strona 1 — zwykły projekt CC
        plain_page = QWidget()
        plain_lay = QVBoxLayout(plain_page)
        plain_lay.setContentsMargins(0, 0, 0, 0)
        plain_lay.setSpacing(8)
        self._plain_meta = QLabel("", styleSheet="color:#9cdcfe;font-size:10px;")
        self._plain_meta.setWordWrap(True)
        plain_lay.addWidget(self._plain_meta)
        msg_lbl = QLabel("Ostatnia wiadomość:", styleSheet="color:#6c7086;font-size:9px;font-weight:bold;letter-spacing:1px;")
        plain_lay.addWidget(msg_lbl)
        self._plain_msg = QPlainTextEdit()
        self._plain_msg.setReadOnly(True)
        self._plain_msg.setFont(_FONT_MONO)
        self._plain_msg.setStyleSheet(
            "QPlainTextEdit{background:#13131e;color:#cdd6f4;font-size:10px;"
            "border:none;border-radius:3px;padding:6px;}"
        )
        plain_lay.addWidget(self._plain_msg, stretch=1)
        self._stack.addWidget(plain_page)  # idx 1

        # strona 2 — pusty slot
        empty_page = QWidget()
        empty_lay = QVBoxLayout(empty_page)
        empty_lbl = QLabel("Brak projektu w tym slocie.")
        empty_lbl.setStyleSheet("color:#3a3a5a;font-size:11px;")
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lay.addWidget(empty_lbl)
        self._stack.addWidget(empty_page)  # idx 2

        rlay.addWidget(self._stack, stretch=1)
        root.addWidget(right, stretch=1)

    # ── Pomocnicze ───────────────────────────────────────────────────────

    def _btn_style(self, color: str, checked: bool) -> str:
        bg = f"{color}22" if checked else "transparent"
        border = f"border-left:3px solid {color};" if checked else f"border-left:3px solid {color}44;"
        return (
            f"QPushButton{{background:{bg};{border}"
            f"border-top:none;border-right:none;border-bottom:none;"
            f"color:#cdd6f4;font-size:10px;text-align:left;padding:4px 10px;}}"
            f"QPushButton:hover{{background:{color}18;}}"
        )

    def _select(self, idx: int) -> None:
        self._selected_idx = idx
        for i, btn in enumerate(self._slot_btns):
            btn.setChecked(i == idx)
            btn.setStyleSheet(self._btn_style(SLOT_COLORS[i], checked=(i == idx)))
        self._render_detail()
        # Przełącz slot w CCLauncherPanel
        p = self.parent()
        while p is not None:
            if hasattr(p, "_slot_tabs"):
                p._slot_tabs.setCurrentIndex(idx)
                break
            p = p.parent()

    def _render_list(self) -> None:
        """Aktualizuje etykiety przycisków listy slotów."""
        for i, d in enumerate(self._slots_data):
            path = d.get("path", "")
            is_sss = d.get("is_sss", False)
            name = d.get("name") or (Path(path).name if path else "—")
            phase = d.get("phase", "")
            phase_dot = "● " if phase == "working" else ("○ " if phase == "waiting" else "  ")
            phase_col = self._PHASE_COLOR.get(phase, "#585b70")

            badge = " [SSS]" if is_sss else ""
            sss_info = ""
            if is_sss and d.get("ssm"):
                s = d["ssm"]
                sss_info = f"\nR{s.current_round or '?'}  ·  sesja {s.session_count}  ·  next {s.next_count}"

            btn = self._slot_btns[i]
            # Użyj rich text przez HTML (QPushButton nie obsługuje) → QLabel wewnątrz
            # Uproszczamy: plain text wieloliniowy
            line1 = f"T{i+1}  {name}{badge}"
            line2 = f"{phase_dot}{phase or 'offline'}{sss_info}"
            btn.setText(f"{line1}\n{line2}")
            btn.setStyleSheet(self._btn_style(SLOT_COLORS[i], checked=(i == self._selected_idx)))
            # Kolor fazy — ustawiamy przez tooltip (nie zmieniamy koloru tekstu per-linia)
            btn.setToolTip(path)

    def _render_detail(self) -> None:
        """Renderuje prawą stronę dla wybranego slotu."""
        if not self._slots_data or self._selected_idx >= len(self._slots_data):
            self._stack.setCurrentIndex(2)
            return

        d = self._slots_data[self._selected_idx]
        path = d.get("path", "")
        is_sss = d.get("is_sss", False)
        name = d.get("name") or (Path(path).name if path else "—")
        phase = d.get("phase", "")
        snap = d.get("snap")
        ssm = d.get("ssm")

        self._det_name.setText(name)
        self._det_badge.setText("SSS" if is_sss else "CC")
        self._det_badge.setStyleSheet(
            "color:#cba6f7;font-size:9px;font-weight:bold;"
            "background:#2a2040;border-radius:3px;padding:1px 5px;"
            if is_sss else
            "color:#89dceb;font-size:9px;font-weight:bold;"
            "background:#0d2030;border-radius:3px;padding:1px 5px;"
        )
        phase_col = self._PHASE_COLOR.get(phase, "#585b70")
        phase_txt = f"● {phase}" if phase else "● offline"
        self._det_phase.setText(phase_txt)
        self._det_phase.setStyleSheet(f"color:{phase_col};font-size:10px;")
        self._det_path.setText(path or "brak ścieżki")

        if not path:
            self._stack.setCurrentIndex(2)
            return

        if is_sss:
            self._stack.setCurrentIndex(0)
            self._render_sss(ssm, snap)
        else:
            self._stack.setCurrentIndex(1)
            self._render_plain(snap)

    def _render_sss(self, ssm, snap) -> None:
        if ssm is not None:
            runda = ssm.current_round or "—"
            sesja = ssm.session_count
            nxt = ssm.next_count
            done = ssm.done_count
            last_ts = ssm.last_event_timestamp[:16].replace("T", " ") if ssm.last_event_timestamp else "—"
            self._sss_meta.setText(
                f"Runda: {runda}  ·  sesja: {sesja}  ·  next: {nxt}  ·  done: {done}  ·  ostatni event: {last_ts}"
            )
        else:
            self._sss_meta.setText("Brak danych SSM — uruchom projekt i zainstaluj hook SSM")

        # Wyczyść bufor
        while self._buf_layout.count() > 1:
            item = self._buf_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        entries = ssm.buffer_entries if ssm else []
        if not entries:
            lbl = QLabel("Bufor jest pusty.")
            lbl.setStyleSheet("color:#3a3a5a;font-size:10px;padding:4px 0;")
            self._buf_layout.insertWidget(0, lbl)
            return

        # Grupujemy: najpierw in_plan (aktywne), potem distributed (rozdzielone)
        active = [e for e in entries if e.status == "in_plan"]
        done_e = [e for e in entries if e.status == "distributed"]

        row_idx = 0
        if active:
            sep_lbl = QLabel(f"AKTYWNE W PLANIE  ({len(active)})",
                styleSheet="color:#6c7086;font-size:8px;font-weight:bold;letter-spacing:1px;padding:4px 0 2px;")
            self._buf_layout.insertWidget(row_idx, sep_lbl)
            row_idx += 1
            for entry in active:
                self._buf_layout.insertWidget(row_idx, self._make_entry_widget(entry))
                row_idx += 1

        if done_e:
            sep_lbl2 = QLabel(f"ROZDZIELONE  ({len(done_e)})",
                styleSheet="color:#3a3a5a;font-size:8px;font-weight:bold;letter-spacing:1px;padding:6px 0 2px;")
            self._buf_layout.insertWidget(row_idx, sep_lbl2)
            row_idx += 1
            for entry in done_e:
                self._buf_layout.insertWidget(row_idx, self._make_entry_widget(entry))
                row_idx += 1

    def _make_entry_widget(self, entry) -> QFrame:
        is_done = entry.status == "distributed"
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background:#1e1e2e;border-radius:3px;border:1px solid #2a2a3a;}"
            if not is_done else
            "QFrame{background:#13131e;border-radius:3px;border:1px solid #1a1a2a;}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(2)

        # Wiersz 1: ikona + target + czas
        top = QHBoxLayout()
        icon = "✓" if is_done else "●"
        icon_col = "#3a3a5a" if is_done else "#cba6f7"
        target_col = "#3a3a5a" if is_done else "#89b4fa"
        lbl_icon = QLabel(icon, styleSheet=f"color:{icon_col};font-size:11px;font-weight:bold;")
        lbl_icon.setFixedWidth(14)
        lbl_target = QLabel(f"[{entry.target}]", styleSheet=f"color:{target_col};font-size:10px;font-weight:bold;")
        ts = entry.timestamp[:16].replace("T", " ") if entry.timestamp else ""
        lbl_ts = QLabel(ts, styleSheet="color:#2a2a4a;font-size:9px;")
        top.addWidget(lbl_icon)
        top.addWidget(lbl_target)
        top.addStretch()
        top.addWidget(lbl_ts)
        lay.addLayout(top)

        # Wiersz 2: treść
        content_col = "#585b70" if is_done else "#cdd6f4"
        lbl_content = QLabel(entry.content)
        lbl_content.setStyleSheet(f"color:{content_col};font-size:10px;")
        lbl_content.setWordWrap(True)
        lay.addWidget(lbl_content)

        # Wiersz 3 (tylko distributed): gdzie trafiło
        if is_done and entry.distributed_to:
            lbl_dest = QLabel(f"→ {entry.distributed_to}", styleSheet="color:#3a3a5a;font-size:9px;")
            lay.addWidget(lbl_dest)

        return frame

    def _render_plain(self, snap) -> None:
        if snap and not snap.is_file_missing:
            parts = []
            if snap.model:
                parts.append(f"model: {snap.model}")
            if snap.cost_usd is not None:
                parts.append(f"koszt: ${snap.cost_usd:.4f}")
            if snap.ctx_pct is not None:
                parts.append(f"ctx: {snap.ctx_pct:.1f}%")
            self._plain_meta.setText("  ·  ".join(parts) if parts else "—")
            self._plain_msg.setPlainText(snap.last_message or "")
        else:
            self._plain_meta.setText("offline")
            self._plain_msg.setPlainText("")

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(
        self,
        slots,
        snaps: dict,
        ssm_snaps: dict,
        active_idx: int,
    ) -> None:
        self._slots_data = []
        for i, slot in enumerate(slots):
            cfg = slot.get_config()
            path = cfg.project_path.strip()
            snap = snaps.get(i + 1)
            phase = ""
            if snap and not snap.is_file_missing:
                phase = snap.phase or ""

            ssm_snap = None
            if slot._is_sss and path:
                try:
                    from src.watchers.process_scanner import norm_path as _np
                    ssm_snap = ssm_snaps.get(_np(path))
                except Exception:
                    pass

            self._slots_data.append({
                "path": path,
                "is_sss": slot._is_sss,
                "name": slot._sss_name if slot._is_sss else "",
                "phase": phase,
                "snap": snap,
                "ssm": ssm_snap,
            })

        self._render_list()
        self._render_detail()


# ──────────────────────────────────────────────────────────────────────────────

class CCLauncherPanel(QWidget):
    """Główny panel 'Sesje CC' z 6 zakładkami slotów projektów (4 robocze + 2 podglądu)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = load_launcher_config()
        self._watcher = SessionWatcher(parent=self)
        self._slots: list[ProjectSlotWidget] = []
        self._plan_watchers: list[object] = [None] * 6  # _SSSPlanWatcher per slot
        self._snap_cache: dict[int, TerminalSnapshot] = {}  # slot_id → last snapshot

        self._active_cwds: set[str] = set()
        self._last_launch: dict[int, float] = {}

        self._setup_ui()
        self._connect_signals()
        self._watcher.start()

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_discovered)
        self._scan_timer.start(10_000)
        QTimer.singleShot(500, self._scan_discovered)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        root.addWidget(self._build_header())

        self._slot_tabs = QTabWidget()
        self._slot_tab_bar = _ColoredSlotTabBar(SLOT_COLORS)
        self._slot_tabs.setTabBar(self._slot_tab_bar)

        # Sloty 1–4: robocze (mają konfigurację)
        for i in range(4):
            slot = ProjectSlotWidget(i + 1, self._config.slots[i], parent=self)
            self._slots.append(slot)
            self._slot_tabs.addTab(slot, SLOT_NAMES[i])
            path = self._config.slots[i].project_path
            self._slot_tab_bar.setSubLabel(i, Path(path).name if path else "—")

        # Sloty 5–6: podgląd (puste konfiguracje, szare kolory)
        from src.cc_launcher.launcher_config import SlotConfig as _SlotConfig
        for i in range(4, 6):
            slot = ProjectSlotWidget(i + 1, _SlotConfig(), parent=self)
            self._slots.append(slot)
            self._slot_tabs.addTab(slot, SLOT_NAMES[i])
            self._slot_tab_bar.setSubLabel(i, "—")

        self._slot_tab_bar.folder_change_requested.connect(self._on_tab_folder_change)

        # MonitorView — jedna instancja per slot, wstawiana do wewnętrznego QTabWidget Config+Monitor
        self._monitor_views: list[_MonitorView] = []
        for slot in self._slots:
            mv = _MonitorView(parent=slot)
            self._monitor_views.append(mv)
            slot.set_monitor_widget(mv)
        self._slot_tabs.currentChanged.connect(self._on_slot_tab_changed)

        self._discovery_panel = _DiscoveryPanel(
            self._get_free_slots,
            self._promote_to_slot,
            parent=self,
        )
        self._discovery_panel.project_lmb.connect(self._on_recent_lmb)
        self._discovery_panel.project_rmb.connect(self._on_recent_rmb)

        content = QWidget()
        content_row = QHBoxLayout(content)
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(4)
        content_row.addWidget(self._slot_tabs, stretch=1)
        content_row.addWidget(self._discovery_panel)
        root.addWidget(content, stretch=1)

    # ── Sloty podglądu (5 = LMB, 6 = RMB) ───────────────────────────────────

    def _set_preview_slot(self, slot_idx: int, path: str) -> None:
        """Ustawia ścieżkę projektu w slocie podglądu (4 = slot5, 5 = slot6)."""
        if not path or not Path(path).is_dir():
            return
        slot = self._slots[slot_idx]
        slot._path_edit.setPlainText(path)
        slot.reload_plan()
        slot.reload_pcc()
        slot.reload_stats()
        slot.reload_history()
        slot.reload_md_files()
        slot.reload_jsonl_transcript()
        slot._notify_sss(path)
        self._slot_tab_bar.setSubLabel(slot_idx, Path(path).name)
        # Przełącz na ten slot żeby user od razu widział zawartość
        self._slot_tabs.setCurrentIndex(slot_idx)

    def _on_recent_lmb(self, path: str) -> None:
        self._set_preview_slot(4, path)  # slot 5 (indeks 4)

    def _on_recent_rmb(self, path: str) -> None:
        self._set_preview_slot(5, path)  # slot 6 (indeks 5)

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

        # Status sync — pojawia się na kilka sekund po synchronizacji
        self._sync_status_lbl = QLabel()
        self._sync_status_lbl.setStyleSheet("font-size:10px;")
        self._sync_status_lbl.hide()
        self._sync_status_timer = QTimer(self)
        self._sync_status_timer.setSingleShot(True)
        self._sync_status_timer.timeout.connect(self._sync_status_lbl.hide)
        row.addWidget(self._sync_status_lbl)

        row.addWidget(QLabel("polling co 15s", styleSheet=_LBL_DIM))

        sync_btn = QPushButton("⇄  Sync cc-panel")
        sync_btn.setStyleSheet(
            "QPushButton{background:#1a2e1a;color:#6ec87e;border:1px solid #2e4a2e;"
            "border-radius:3px;padding:4px 12px}"
            "QPushButton:hover{background:#243e24}"
            "QPushButton:pressed{background:#1a2e1a}"
        )
        sync_btn.setFont(_FONT_SMALL)
        sync_btn.setToolTip(
            "Synchronizuje ścieżki projektów między cc-panel (ustawienia.json)\n"
            "a slotami CM. Kierunek: cc-panel → slot (gdy cc-panel ma ścieżkę);\n"
            "slot → cc-panel (gdy tylko CM ma ścieżkę)."
        )
        sync_btn.clicked.connect(self._sync_with_ccpanel)
        row.addWidget(sync_btn)

        ssm_btn = QPushButton("⚙ Zainstaluj hook SSM")
        ssm_btn.setStyleSheet(_BTN)
        ssm_btn.setFont(_FONT_SMALL)
        ssm_btn.setToolTip("Instaluje hook SessionStart SSM w aktywnym projekcie SSS")
        ssm_btn.clicked.connect(self._on_install_ssm_hook)
        row.addWidget(ssm_btn)

        btn = QPushButton("⟳  Odśwież")
        btn.setStyleSheet(_BTN)
        btn.setFont(_FONT_MONO)
        btn.clicked.connect(self._watcher.force_refresh)
        row.addWidget(btn)
        return w

    def _on_install_ssm_hook(self) -> None:
        """Instaluje hook SessionStart SSM w projekcie z aktywnego slotu."""
        try:
            from src.ssm_module.core.hook_installer import install_hook, is_sss_project
        except ImportError:
            QMessageBox.warning(self, "SSM niedostępny", "Moduł SSM nie jest załadowany.")
            return

        idx = self._slot_tabs.currentIndex()
        slot_cfg = self._config.slots[idx] if 0 <= idx < len(self._config.slots) else None
        path_str = slot_cfg.project_path if slot_cfg else ""
        if not path_str:
            QMessageBox.warning(self, "Brak projektu", "Aktywny slot nie ma ustawionego katalogu projektu.")
            return

        path = Path(path_str)
        if not is_sss_project(path):
            QMessageBox.warning(
                self, "Nie jest projektem SSS",
                f"{path.name} nie zawiera PLAN.md z markerem SSS.\n"
                "Hook można zainstalować tylko w projektach inicjalizowanych przez SSS."
            )
            return

        result = install_hook(path)
        if result.already_installed:
            QMessageBox.information(self, "Hook SSM", f"Hook SSM jest już zainstalowany w {path.name}.")
        elif result.success:
            QMessageBox.information(self, "Hook SSM", f"Hook SSM zainstalowany pomyślnie w {path.name}.")
        else:
            QMessageBox.critical(self, "Błąd instalacji", result.message)

    def _on_global_term_changed(self, n: int) -> None:
        self._config.terminal_count = max(1, min(4, int(n)))
        save_launcher_config(self._config)

    # ── Synchronizacja z cc-panel ──────────────────────────────────────────

    def _sync_with_ccpanel(self) -> None:
        """Synchronizuje ścieżki projektów między cc-panel a slotami CM.

        Kierunek dla każdego slotu i (0–3):
        - cc-panel ma ścieżkę → nadpisuje slot CM (cc-panel = źródło aktywnej sesji)
        - slot CM ma ścieżkę, cc-panel nie ma → zapisuje do cc-panel
        - oba mają tę samą ścieżkę → brak akcji
        Po synchronizacji wymusza odczyt metryk (force_refresh) i rescan procesów.
        """
        import json as _json

        _CCPANEL_DIR = Path.home() / ".claude" / "cc-panel"
        settings_path = _CCPANEL_DIR / "ustawienia.json"

        # Wczytaj ustawienia cc-panel
        try:
            if settings_path.exists():
                data: dict = _json.loads(settings_path.read_text(encoding="utf-8"))
            else:
                data = {}
        except Exception:
            data = {}

        raw_paths = data.get("projectPaths", [])
        if not isinstance(raw_paths, list):
            raw_paths = []
        cc_paths: list[str] = (raw_paths + ["", "", "", ""])[:4]

        synced_to_cm = 0
        synced_to_cc = 0

        for i, slot in enumerate(self._slots[:4]):
            cm_path = slot.get_config().project_path.strip()
            cc_path = cc_paths[i].strip()

            if cc_path and cc_path != cm_path:
                # cc-panel → CM: cc-panel jest źródłem aktywnych sesji
                slot._path_edit.setPlainText(cc_path)
                slot.reload_plan()
                slot.reload_stats()
                slot.reload_md_files()
                slot._notify_sss(cc_path)
                synced_to_cm += 1

            elif cm_path and not cc_path:
                # CM → cc-panel: slot CM ma projekt, terminal cc-panel pusty
                cc_paths[i] = cm_path
                synced_to_cc += 1

        # Zapisz zaktualizowane ścieżki do ustawienia.json
        data["projectPaths"] = cc_paths
        try:
            _CCPANEL_DIR.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                _json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            import sys as _sys
            print(f"[sync] zapis ustawienia.json nie powiódł się: {exc}", file=_sys.stderr)

        # Wymuś odczyt metryk i rescan procesów
        self._on_config_changed()
        self._watcher.force_refresh()
        QTimer.singleShot(500, self._scan_discovered)

        # Pokaż wynik w nagłówku
        total = synced_to_cm + synced_to_cc
        if total == 0:
            self._show_sync_status("✓ Sloty już zsynchronizowane", "#6ec87e")
        else:
            parts = []
            if synced_to_cm:
                parts.append(f"cc→CM: {synced_to_cm}")
            if synced_to_cc:
                parts.append(f"CM→cc: {synced_to_cc}")
            self._show_sync_status(f"✓ Zsynchronizowano ({', '.join(parts)})", "#6ec87e")

    def _show_sync_status(self, text: str, color: str = "#6ec87e", duration_ms: int = 4_000) -> None:
        """Pokazuje komunikat statusu synchronizacji w nagłówku przez duration_ms ms."""
        self._sync_status_lbl.setText(text)
        self._sync_status_lbl.setStyleSheet(f"color:{color};font-size:10px;")
        self._sync_status_lbl.show()
        self._sync_status_timer.start(duration_ms)

    # ───────────────────────────────────────────────────────────────────────

    def _on_tab_folder_change(self, idx: int) -> None:
        """Otwiera dialog wyboru folderu dla slotu idx (podwójny prawy klik na zakładce)."""
        if 0 <= idx < len(self._slots):
            self._slot_tabs.setCurrentIndex(idx)
            self._slots[idx]._on_browse()

    def _connect_signals(self) -> None:
        if getattr(self, "_signals_connected", False):
            print("[CC Launcher] WARNING: _connect_signals called more than once!")
        self._signals_connected = True
        self._watcher.snapshot_updated.connect(self._on_snapshot)
        for slot in self._slots:
            slot.config_changed.connect(self._on_config_changed)
            slot.launch_requested.connect(self._on_launch)
            slot.window_requested.connect(self._on_window)
            slot.stop_requested.connect(self._on_stop)
            slot.stop_completed.connect(self._on_stop_completed)
            slot.sss_detected.connect(self._on_sss_detected)
            slot._tabs.currentChanged.connect(self._on_section_tab_changed)

        # Wykryj SSS v2 dla slotów już wczytanych z konfiguracji
        from PySide6.QtCore import QTimer as _QT
        _QT.singleShot(0, self._detect_sss_all_slots)

    def _on_slot_tab_changed(self, idx: int) -> None:
        """Odświeża Monitor gdy user przełączy slot. Zachowuje aktywną sekcję."""
        # Zachowaj indeks sekcji z poprzedniego slotu i ustaw go w nowym
        prev_section = getattr(self, "_last_section_idx", 0)
        self._slots[idx]._tabs.setCurrentIndex(prev_section)
        self._refresh_monitor()

    def _on_section_tab_changed(self, section_idx: int) -> None:
        """Zapamiętuje aktywną sekcję przy każdej zmianie."""
        self._last_section_idx = section_idx

    def _refresh_monitor(self) -> None:
        # ssm_snaps: norm(path) → ProjectSnapshot
        ssm_snaps: dict = {}
        if _SSM_AVAILABLE:
            try:
                from src.ssm_module.core.ssm_service import SSMService as _Svc
                from src.watchers.process_scanner import norm_path as _np
                svc = _Svc.instance()
                for entry in svc.projects():
                    s = svc.snapshot(entry.project_id)
                    if s is not None:
                        ssm_snaps[_np(entry.path)] = s
            except Exception:
                pass
        active_idx = self._slot_tabs.currentIndex()
        for mv in self._monitor_views:
            mv.refresh(
                slots=self._slots,
                snaps=self._snap_cache,
                ssm_snaps=ssm_snaps,
                active_idx=active_idx,
            )

    def _on_snapshot(self, snap: TerminalSnapshot) -> None:
        self._slots[snap.slot_id - 1].update_snapshot(snap)
        self._snap_cache[snap.slot_id] = snap

        # Weryfikacja procesem — jeśli CC nie działa w tym folderze, wymuś offline
        from src.watchers.process_scanner import norm_path
        from datetime import datetime, timezone
        slot_path = self._config.slots[snap.slot_id - 1].project_path
        has_proc = bool(slot_path and norm_path(slot_path) in self._active_cwds)

        # Elapsed time ze źródła — ostatni timestamp w transkrypcie
        elapsed = ""
        if has_proc and snap.transcript_path:
            last_ts = read_last_activity_ts(snap.transcript_path)
            if last_ts:
                delta = datetime.now(timezone.utc) - last_ts
                s = max(0, int(delta.total_seconds()))
                mins, secs = divmod(s, 60)
                hrs, mins = divmod(mins, 60)
                if hrs:
                    elapsed = f"{hrs}h {mins}m"
                elif mins:
                    elapsed = f"{mins}m {secs:02d}s"
                else:
                    elapsed = f"{secs}s"

        self._slot_tab_bar.setStatusLabel(
            index=snap.slot_id - 1,
            phase=snap.phase if has_proc else None,
            elapsed=elapsed,
            is_missing=snap.is_file_missing or not has_proc,
        )
        self._refresh_monitor()

    def _on_config_changed(self) -> None:
        for i, slot in enumerate(self._slots[:4]):
            self._config.slots[i] = slot.get_config()
            path = self._config.slots[i].project_path
            if not slot._is_sss:
                self._slot_tab_bar.setSubLabel(i, Path(path).name if path else "—")
        save_launcher_config(self._config)

    def assign_project(self, path: Path) -> int:
        """Assign a new project path to the first empty slot (or slot 1 as fallback).

        Returns the 1-based slot number that received the project.
        Switches the tab to that slot automatically.
        """
        from pathlib import Path as _Path
        target = 1
        for i, slot in enumerate(self._slots[:4]):
            if not slot.get_config().project_path.strip():
                target = i + 1
                break

        slot_widget = self._slots[target - 1]
        slot_widget._path_edit.setPlainText(str(path))
        slot_widget.reload_plan()
        slot_widget.reload_stats()
        slot_widget.reload_md_files()
        slot_widget._notify_sss(str(path))
        self._slot_tabs.setCurrentIndex(target - 1)
        return target

    def _get_free_slots(self) -> list[int]:
        """Zwraca numery slotów roboczych (1–4) bez przypisanego projektu."""
        return [
            i + 1 for i, slot in enumerate(self._slots[:4])
            if not slot.get_config().project_path.strip()
        ]

    def _scan_discovered(self) -> None:
        """Skanuje procesy systemowe, aktualizuje statusy slotów i discovery panel."""
        from src.watchers.process_scanner import scan_cc_processes, norm_path
        all_sessions = scan_cc_processes()
        self._active_cwds = {norm_path(s.cwd) for s in all_sessions}

        # Mapa: norm_path(cwd) → slot_id (1–4) dla slotów z projektem
        slot_assignment: dict[str, int] = {
            norm_path(cfg.project_path): i + 1
            for i, cfg in enumerate(self._config.slots)
            if cfg.project_path
        }

        # Wszystkie sesje trafiają do panelu (max 8), każda wie czy jest zarządzana
        self._discovery_panel.refresh(all_sessions[:8], slot_assignment)

        # Wymuś offline dla slotów bez aktywnego procesu CC
        for i, cfg_slot in enumerate(self._config.slots):
            if cfg_slot.project_path and norm_path(cfg_slot.project_path) not in self._active_cwds:
                self._slot_tab_bar.setStatusLabel(
                    index=i, phase=None, elapsed="", is_missing=True,
                )

    def _promote_to_slot(self, cwd: str, slot_id: int) -> None:
        """Przypisuje wykrytą sesję CC do wybranego slotu."""
        slot_widget = self._slots[slot_id - 1]
        slot_widget._path_edit.setPlainText(cwd)
        slot_widget.reload_plan()
        slot_widget.reload_stats()
        slot_widget.reload_md_files()
        slot_widget._notify_sss(cwd)
        self._slot_tabs.setCurrentIndex(slot_id - 1)
        self._on_config_changed()
        QTimer.singleShot(500, self._scan_discovered)

    _LAUNCH_DEBOUNCE_S: float = 5.0

    def _on_launch(self, slot_id: int) -> None:
        now = time.monotonic()
        last = self._last_launch.get(slot_id, 0.0)
        elapsed = now - last
        print(
            f"[CC Launcher] _on_launch slot={slot_id} terminals={self._config.terminal_count}"
            f" ts={now:.3f} elapsed_since_last={elapsed:.2f}s"
        )
        if elapsed < self._LAUNCH_DEBOUNCE_S:
            print(f"[CC Launcher] _on_launch slot={slot_id} DEBOUNCE (elapsed={elapsed:.2f}s < {self._LAUNCH_DEBOUNCE_S}s)")
            return
        self._last_launch[slot_id] = now

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

        # Sync cc-panel jeśli projekt SSS v2
        if self._slots[slot_id - 1]._is_sss:
            self._sync_ccpanel_path(slot_id, cfg.project_path)

        ok = prepare_and_launch(
            slot_id=slot_id,
            project_path=cfg.project_path,
            terminal_count=self._config.terminal_count,
            vibe_prompt=cfg.vibe_prompt,
            model=cfg.model,
            permission_flag=CC_PERMISSION_MODES.get(cfg.permission_mode, ""),
            pre_command=cfg.pre_command,
            cc_flags=cfg.cc_flags,
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

    # ------------------------------------------------------------------ #
    # SSS v2 — detekcja, PlanWatcher, sync cc-panel                        #
    # ------------------------------------------------------------------ #

    def _detect_sss_all_slots(self) -> None:
        """Wykrywa SSS v2 dla wszystkich slotów z już załadowaną ścieżką."""
        for slot in self._slots:
            path = slot.get_config().project_path.strip()
            slot._notify_sss(path)

    def _on_sss_detected(self, slot_id: int, is_sss: bool, project_name: str) -> None:
        """Obsługuje wykrycie (lub brak) projektu SSS v2 w slocie."""
        idx = slot_id - 1
        if idx >= len(self._config.slots):
            return  # preview slots (5, 6) nie mają SlotConfig w konfiguracji
        self._slot_tab_bar.setSssFlag(idx, is_sss)

        # Sub-label zawsze pokazuje nazwę folderu — badge SSS informuje o typie projektu
        path = self._config.slots[idx].project_path
        self._slot_tab_bar.setSubLabel(idx, Path(path).name if path else "—")

        if not is_sss:
            self._slot_tab_bar.setSssPlanText(idx, "")

        # Zarządzaj PlanWatcher
        old = self._plan_watchers[idx]
        if old is not None:
            try:
                old.stop()
            except Exception:
                pass
            self._plan_watchers[idx] = None

        if is_sss and _SSS_AVAILABLE:
            path = self._config.slots[idx].project_path
            plan_path = Path(path) / "PLAN.md"
            if plan_path.exists():
                watcher = _SSSPlanWatcher(plan_path, parent=self)
                watcher.qt_plan_changed.connect(
                    lambda sections, i=idx: self._on_plan_changed(i, sections)
                )
                watcher.start()
                self._plan_watchers[idx] = watcher

        self._refresh_monitor()

    def _on_plan_changed(self, slot_idx: int, sections: dict) -> None:
        """Aktualizuje tekst planu w tab barze po zmianie PLAN.md."""
        meta = sections.get("meta", "")
        status = ""
        session = ""
        for line in meta.splitlines():
            line = line.strip().lstrip("- ")
            if line.startswith("status:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("session:"):
                session = line.split(":", 1)[1].strip()
        if status or session:
            plan_text = f"📋 {status}" + (f" · sesja {session}" if session else "")
            self._slot_tab_bar.setSssPlanText(slot_idx, plan_text)

    def _sync_ccpanel_path(self, slot_id: int, path: str) -> None:
        """Synchronizuje ścieżkę projektu SSS v2 do cc-panel ustawienia.json."""
        import sys as _sys
        settings_path = Path.home() / ".claude" / "cc-panel" / "ustawienia.json"
        try:
            data = (
                json.loads(settings_path.read_text(encoding="utf-8"))
                if settings_path.exists() else {}
            )
            paths: list[str] = data.get("projectPaths", ["", "", "", ""])
            paths = (paths + ["", "", "", ""])[:4]
            paths[slot_id - 1] = path
            data["projectPaths"] = paths
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[SSS] cc-panel sync failed: {exc}", file=_sys.stderr)

    # ------------------------------------------------------------------ #
    # Nawigacja do zakładek SSM / SSC w aktywnym slocie                    #
    # ------------------------------------------------------------------ #

    _TAB_SSC_IN_SLOT = 7   # indeks zewnętrznej zakładki "Full Converter" w ProjectSlotWidget

    def show_ssm_tab(self) -> None:
        """Przełącza aktywny slot na zakładkę Monitor (wewnątrz Config)."""
        idx = self._slot_tabs.currentIndex()
        if 0 <= idx < len(self._slots):
            slot = self._slots[idx]
            slot._tabs.setCurrentIndex(0)           # zewnętrzna: Config
            slot._inner_config_tabs.setCurrentIndex(1)  # wewnętrzna: Monitor

    def show_ssc_tab(self) -> None:
        """Przełącza aktywny slot na zakładkę Full Converter (SSC)."""
        idx = self._slot_tabs.currentIndex()
        if 0 <= idx < len(self._slots):
            self._slots[idx]._tabs.setCurrentIndex(self._TAB_SSC_IN_SLOT)


def _wrap(layout: QHBoxLayout) -> QWidget:
    """Owija QHBoxLayout w QWidget do użycia w _kv_row."""
    w = QWidget()
    w.setLayout(layout)
    return w
