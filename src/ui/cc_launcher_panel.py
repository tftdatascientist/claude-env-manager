"""Panel 'Sesje CC' — uruchamianie i monitorowanie sesji Claude Code."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
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
    fmt_duration,
    get_session_history,
)
from src.cc_launcher.session_manager import (
    open_vscode_window,
    prepare_and_launch,
    terminate_vscode_session,
)
from src.utils.plan_parser import PlanData, get_section, read_plan, write_plan
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


class ProjectSlotWidget(QWidget):
    """Widget jednego slotu — 5 zakładek: Dane, PLAN, Historia, Sesje, Vibe Code."""

    config_changed = Signal()
    launch_requested = Signal(int)
    window_requested = Signal(int)
    stop_requested = Signal(int)

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
        self._tabs.addTab(self._build_plan(), "PLAN")
        self._tabs.addTab(self._build_historia(), "Historia")
        self._tabs.addTab(self._build_sesje(), "Sesje")
        self._tabs.addTab(self._build_vibe(), "Vibe Code")

        root.addWidget(_sep())
        root.addWidget(self._build_action_bar())

    # ---- Dane ---------------------------------------------------------- #

    def _build_dane(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # ---- Ścieżka projektu ----
        lay.addWidget(QLabel("Ścieżka projektu", styleSheet=_LBL_HEAD))
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
        lay.addLayout(path_row)

        # ---- Konfiguracja startowa ----
        lay.addWidget(_sep())
        lay.addWidget(QLabel("Konfiguracja startowa", styleSheet=_LBL_HEAD))

        self._model_combo = QComboBox()
        self._model_combo.addItems(CC_MODELS)
        self._model_combo.setFont(_FONT_MONO)
        lay.addLayout(_kv_row("Model:", self._model_combo))

        self._effort_combo = QComboBox()
        self._effort_combo.addItems(CC_EFFORTS)
        self._effort_combo.setFont(_FONT_MONO)
        lay.addLayout(_kv_row("Effort:", self._effort_combo))

        self._perm_combo = QComboBox()
        self._perm_combo.addItems(list(CC_PERMISSION_MODES.keys()))
        self._perm_combo.setFont(_FONT_MONO)
        lay.addLayout(_kv_row("Uprawnienia:", self._perm_combo))

        term_row = QHBoxLayout()
        term_row.setSpacing(4)
        self._term_spin = QSpinBox()
        self._term_spin.setRange(1, 4)
        self._term_spin.setValue(1)
        self._term_spin.setFont(_FONT_MONO)
        self._term_spin.setFixedWidth(55)
        term_row.addWidget(self._term_spin)
        for n in range(1, 5):
            dot = QLabel(f"●{n}", styleSheet=f"color:{SLOT_COLORS[n-1]};font-size:11px;")
            term_row.addWidget(dot)
        term_row.addStretch()
        lay.addLayout(_kv_row("Terminale CC:", _wrap(term_row)))

        # ---- Stan sesji ----
        lay.addWidget(_sep())
        lay.addWidget(QLabel("Stan aktywnej sesji", styleSheet=_LBL_HEAD))
        card = QFrame()
        card.setStyleSheet(_CARD)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(8, 6, 8, 6)
        card_lay.setSpacing(2)
        self._lbl_phase = _val()
        self._lbl_model_live = _val()
        self._lbl_cost = _val()
        self._lbl_ctx = _val()
        card_lay.addLayout(_kv_row("Faza:", self._lbl_phase))
        card_lay.addLayout(_kv_row("Model:", self._lbl_model_live))
        card_lay.addLayout(_kv_row("Koszt:", self._lbl_cost))
        card_lay.addLayout(_kv_row("Ctx%:", self._lbl_ctx))
        lay.addWidget(card)

        # ---- Statystyki projektu ----
        lay.addWidget(_sep())
        stats_hdr = QHBoxLayout()
        stats_hdr.addWidget(QLabel("Statystyki projektu", styleSheet=_LBL_HEAD))
        stats_hdr.addStretch()
        self._btn_stats_refresh = QPushButton("⟳")
        self._btn_stats_refresh.setFixedWidth(28)
        self._btn_stats_refresh.setStyleSheet(_BTN)
        stats_hdr.addWidget(self._btn_stats_refresh)
        lay.addLayout(stats_hdr)

        stats_card = QFrame()
        stats_card.setStyleSheet(_CARD)
        sc_lay = QVBoxLayout(stats_card)
        sc_lay.setContentsMargins(8, 6, 8, 6)
        sc_lay.setSpacing(2)

        self._lbl_files = _val()
        self._lbl_size = _val()
        self._lbl_git = _val()
        self._lbl_git_url = _val()
        self._lbl_branch = _val()
        sc_lay.addLayout(_kv_row("Pliki/foldery:", self._lbl_files))
        sc_lay.addLayout(_kv_row("Rozmiar:", self._lbl_size))
        sc_lay.addLayout(_kv_row("Git:", self._lbl_git))
        sc_lay.addLayout(_kv_row("Remote:", self._lbl_git_url))
        sc_lay.addLayout(_kv_row("Gałąź:", self._lbl_branch))
        lay.addWidget(stats_card)

        # Kluczowe pliki
        lay.addWidget(QLabel("Kluczowe pliki projektu", styleSheet=_LBL_HEAD))
        kf_card = QFrame()
        kf_card.setStyleSheet(_CARD)
        kf_lay = QVBoxLayout(kf_card)
        kf_lay.setContentsMargins(8, 6, 8, 6)
        kf_lay.setSpacing(2)
        self._key_file_labels: dict[str, QLabel] = {}
        from src.cc_launcher.project_stats import KEY_FILES
        for fname in KEY_FILES:
            lbl = _val("—", _LBL_DIM)
            self._key_file_labels[fname] = lbl
            kf_lay.addLayout(_kv_row(fname + ":", lbl))
        lay.addWidget(kf_card)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
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

        # Podsumowanie
        sum_card = QFrame()
        sum_card.setStyleSheet(_CARD)
        sum_lay = QVBoxLayout(sum_card)
        sum_lay.setContentsMargins(8, 6, 8, 6)
        sum_lay.setSpacing(2)
        self._lbl_cc_sessions = _val()
        self._lbl_cc_last = _val()
        self._lbl_aa_sessions = _val()
        self._lbl_aa_cost = _val()
        self._lbl_aa_time = _val()
        self._lbl_aa_last = _val()
        sum_lay.addLayout(_kv_row("Sesje CC (pliki):", self._lbl_cc_sessions))
        sum_lay.addLayout(_kv_row("Ostatnia CC:", self._lbl_cc_last))
        sum_lay.addLayout(_kv_row("Sesje AA:", self._lbl_aa_sessions))
        sum_lay.addLayout(_kv_row("Koszt AA (łącznie):", self._lbl_aa_cost))
        sum_lay.addLayout(_kv_row("Czas AA (łącznie):", self._lbl_aa_time))
        sum_lay.addLayout(_kv_row("Ostatnia AA:", self._lbl_aa_last))
        lay.addWidget(sum_card)

        # Lista ostatnich sesji AA
        lay.addWidget(QLabel("Ostatnie sesje Auto-Accept:", styleSheet=_LBL_KEY))
        self._sesje_list = QPlainTextEdit()
        self._sesje_list.setReadOnly(True)
        self._sesje_list.setFont(_FONT_MONO)
        self._sesje_list.setPlaceholderText("Brak sesji AA lub brak pliku aa-sessions.jsonl")
        lay.addWidget(self._sesje_list, stretch=1)
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

        self._btn_stop = QPushButton("KONIEC")
        self._btn_stop.setStyleSheet(_BTN_DANGER)
        self._btn_stop.setFont(_FONT_MONO)
        self._btn_stop.setToolTip("Zatrzymaj sesję Auto-Accept CC")

        row.addWidget(self._btn_launch, stretch=2)
        row.addWidget(self._btn_window)
        row.addWidget(self._btn_stop)
        return w

    # ------------------------------------------------------------------ #
    # Sygnały                                                               #
    # ------------------------------------------------------------------ #

    def _connect_signals(self) -> None:
        self._btn_launch.clicked.connect(lambda: self.launch_requested.emit(self._slot_id))
        self._btn_window.clicked.connect(lambda: self.window_requested.emit(self._slot_id))
        self._btn_stop.clicked.connect(lambda: self.stop_requested.emit(self._slot_id))
        self._btn_browse.clicked.connect(self._on_browse)
        self._btn_plan_refresh.clicked.connect(self.reload_plan)
        self._btn_plan_save.clicked.connect(self._on_plan_save)
        self._btn_hist_refresh.clicked.connect(self._refresh_transcript)
        self._btn_stats_refresh.clicked.connect(self.reload_stats)
        self._btn_sesje_refresh.clicked.connect(self.reload_history)

        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._vibe_edit.textChanged,
        ):
            sig.connect(self._on_config_changed)
        self._term_spin.valueChanged.connect(self._on_config_changed)
        self._plan_editor.textChanged.connect(lambda: self._btn_plan_save.setEnabled(True))

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
            terminal_count=self._term_spin.value(),
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
        self._term_spin.valueChanged.disconnect(self._on_config_changed)

        self._path_edit.setPlainText(self._config.project_path)
        idx = self._model_combo.findText(self._config.model)
        self._model_combo.setCurrentIndex(max(0, idx))
        idx = self._effort_combo.findText(self._config.effort)
        self._effort_combo.setCurrentIndex(max(0, idx))
        idx = self._perm_combo.findText(self._config.permission_mode)
        self._perm_combo.setCurrentIndex(max(0, idx))
        self._term_spin.setValue(max(1, min(4, self._config.terminal_count)))
        self._vibe_edit.setPlainText(self._config.vibe_prompt)

        for sig in (
            self._path_edit.textChanged,
            self._model_combo.currentIndexChanged,
            self._effort_combo.currentIndexChanged,
            self._perm_combo.currentIndexChanged,
            self._vibe_edit.textChanged,
        ):
            sig.connect(self._on_config_changed)
        self._term_spin.valueChanged.connect(self._on_config_changed)

        if self._config.project_path:
            self._lbl_plan_path.setText(
                str(Path(self._config.project_path) / "PLAN.md")
            )
            self.reload_plan()
            self.reload_stats()
            self.reload_history()

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
            self.reload_stats()
            self.reload_history()

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

        # Sesje Auto-Accept
        self._lbl_aa_sessions.setText(str(h.aa_session_count))
        self._lbl_aa_cost.setText(f"${h.aa_total_cost_usd:.4f}" if h.aa_session_count else "—")
        self._lbl_aa_time.setText(
            fmt_duration(h.aa_total_duration_s) if h.aa_total_duration_s else "—"
        )
        if h.aa_last_session_at:
            self._lbl_aa_last.setText(
                h.aa_last_session_at.strftime("%Y-%m-%d %H:%M")
            )
        else:
            self._lbl_aa_last.setText("—")

        # Lista sesji
        if not h.aa_sessions:
            self._sesje_list.setPlainText("Brak sesji Auto-Accept dla tego slotu.")
            return
        lines = []
        for rec in h.aa_sessions:
            date = rec.started_at.strftime("%m-%d %H:%M") if rec.started_at else "?"
            dur = fmt_duration(rec.duration_s) if rec.duration_s else "w toku"
            cost = f"${rec.total_cost_usd:.3f}"
            reason = rec.stop_reason or "?"
            lines.append(
                f"{date}  {dur:>9}  {cost:>7}  {rec.iterations:>3} iter  [{reason}]"
            )
        self._sesje_list.setPlainText("\n".join(lines))

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
        # Zakładki projektów — duże i pogrubione jak nagłówek panelu
        tab_font = QFont("Segoe UI", 12)
        tab_font.setBold(True)
        self._slot_tabs.tabBar().setFont(tab_font)
        self._slot_tabs.setStyleSheet(
            "QTabBar::tab { padding: 7px 22px; min-width: 90px; }"
        )
        for i in range(4):
            slot = ProjectSlotWidget(i + 1, self._config.slots[i], parent=self)
            self._slots.append(slot)
            self._slot_tabs.addTab(slot, SLOT_NAMES[i])
            self._slot_tabs.tabBar().setTabTextColor(i, QColor(SLOT_COLORS[i]))
        root.addWidget(self._slot_tabs, stretch=1)

    def _build_header(self) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(4, 2, 4, 2)
        title = QLabel("Sesje Claude Code")
        title.setStyleSheet("color:#cccccc;font-size:13px;font-weight:bold;")
        row.addWidget(title)
        row.addStretch()
        row.addWidget(QLabel("polling co 15s", styleSheet=_LBL_DIM))
        btn = QPushButton("⟳  Odśwież")
        btn.setStyleSheet(_BTN)
        btn.setFont(_FONT_MONO)
        btn.clicked.connect(self._watcher.force_refresh)
        row.addWidget(btn)
        return w

    def _connect_signals(self) -> None:
        self._watcher.snapshot_updated.connect(self._on_snapshot)
        for slot in self._slots:
            slot.config_changed.connect(self._on_config_changed)
            slot.launch_requested.connect(self._on_launch)
            slot.window_requested.connect(self._on_window)
            slot.stop_requested.connect(self._on_stop)

    def _on_snapshot(self, snap: TerminalSnapshot) -> None:
        self._slots[snap.slot_id - 1].update_snapshot(snap)

    def _on_config_changed(self) -> None:
        for i, slot in enumerate(self._slots):
            self._config.slots[i] = slot.get_config()
        save_launcher_config(self._config)

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
            terminal_count=cfg.terminal_count,
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
        reply = QMessageBox.question(
            self, "Zakończ sesję CC",
            f"Zatrzymać Auto-Accept dla Slotu {slot_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            terminate_vscode_session(slot_id)
            QTimer.singleShot(1000, self._watcher.force_refresh)


def _wrap(layout: QHBoxLayout) -> QWidget:
    """Owija QHBoxLayout w QWidget do użycia w _kv_row."""
    w = QWidget()
    w.setLayout(layout)
    return w
