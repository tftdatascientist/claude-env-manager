"""Panel 'Zadania' — zarządzanie zadaniami w plikach PLAN.md (format DPS)."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
_BTN_GREEN = (
    "QPushButton{background:#1a3a1a;color:#98c379;"
    "border:1px solid #2a5a2a;border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#2a5a2a}"
)
_BTN_WARN = (
    "QPushButton{background:#3a2a00;color:#e5c07b;"
    "border:1px solid #5a4000;border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#5a4000}"
)
_BTN_PURPLE = (
    "QPushButton{background:#2a1a3a;color:#c678dd;"
    "border:1px solid #4a2a5a;border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#4a2a5a}"
    "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
)
_CARD = (
    "QFrame{background:#1e1e1e;border:1px solid #3c3c3c;"
    "border-radius:4px;padding:2px}"
)
_LBL_HEAD = "color:#9cdcfe;font-size:11px;font-weight:bold;"
_LBL_KEY = "color:#9cdcfe;font-size:10px;"
_LBL_VAL = "color:#cccccc;font-size:10px;"
_LBL_DIM = "color:#5c6370;font-size:10px;"
_LBL_OK = "color:#98c379;font-size:10px;"
_LBL_WARN = "color:#e5c07b;font-size:10px;"
_LBL_ERR = "color:#e06c75;font-size:10px;"

_RE_DPS_META = re.compile(r"<!--\s*PLAN\s+v[\d.]+\s*-->", re.IGNORECASE)
_RE_SECTION = re.compile(
    r"<!--\s*SECTION:(\w+)\s*-->(.*?)<!--\s*/SECTION:\1\s*-->", re.DOTALL
)

_DPS_TEMPLATE = """\
<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal:
- session: 1
- updated: {ts}
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task:
- file:
- started:
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- {ts} | Plik utworzony przez ZadaniaPanel
<!-- /SECTION:session_log -->
"""

# Tryby AI — (etykieta, opis w placeholderze, szablon promptu)
_AI_MODES: list[tuple[str, str, str]] = [
    (
        "Generuj zadania",
        "Opisz cel, kontekst i stan projektu. AI wygeneruje listę zadań do sekcji Next.",
        (
            "Jesteś asystentem planowania projektów.\n"
            "Na podstawie poniższego kontekstu wygeneruj konkretną listę zadań "
            "do wykonania w najbliższej sesji pracy.\n"
            "Format odpowiedzi: wyłącznie lista w stylu markdown:\n"
            "- [ ] Zadanie 1\n- [ ] Zadanie 2\n...\n\n"
            "Kontekst planu:\n{plan_context}\n\n"
            "Dodatkowe informacje od użytkownika:\n{user_input}"
        ),
    ),
    (
        "Do-planowanie",
        "Opisz które zadanie chcesz rozłożyć na mniejsze kroki lub zmienić podejście.",
        (
            "Jesteś asystentem planowania projektów.\n"
            "Zadanie do doprecyzowania:\n{user_input}\n\n"
            "Kontekst planu:\n{plan_context}\n\n"
            "Rozłóż to zadanie na konkretne, małe kroki. "
            "Odpowiedz wyłącznie listą markdown:\n- [ ] Krok 1\n- [ ] Krok 2\n..."
        ),
    ),
    (
        "Nadinterpretacja",
        "AI zanalizuje plan i wskaże nieoczywiste ryzyka, zależności i brakujące kroki.",
        (
            "Jesteś doświadczonym recenzentem planów projektowych.\n"
            "Przeanalizuj poniższy plan i wskaż:\n"
            "1. Nieoczywiste ryzyka i problemy\n"
            "2. Brakujące kroki lub zależności\n"
            "3. Sugestie usprawnień\n\n"
            "Plan:\n{plan_context}\n\n"
            "Uwagi użytkownika:\n{user_input}"
        ),
    ),
    (
        "PLAN B",
        "Opisz problem lub blokadę. AI zaproponuje alternatywne podejście.",
        (
            "Jesteś asystentem rozwiązywania problemów projektowych.\n"
            "Pierwotny plan lub problem:\n{plan_context}\n\n"
            "Blokada lub problem opisany przez użytkownika:\n{user_input}\n\n"
            "Zaproponuj alternatywne podejście (PLAN B). "
            "Zacznij od krótkiego opisu strategii, potem lista kroków markdown:\n"
            "- [ ] Krok 1\n- [ ] Krok 2\n..."
        ),
    ),
]


def _is_dps(text: str) -> bool:
    return bool(_RE_DPS_META.search(text))


def _read_section(text: str, name: str) -> str:
    for m in _RE_SECTION.finditer(text):
        if m.group(1).lower() == name.lower():
            return m.group(2).strip()
    return ""


def _replace_section(text: str, name: str, new_body: str) -> str:
    tag_open = f"<!-- SECTION:{name} -->"
    tag_close = f"<!-- /SECTION:{name} -->"
    pattern = re.compile(
        re.escape(tag_open) + r"(.*?)" + re.escape(tag_close), re.DOTALL
    )
    replacement = f"{tag_open}\n{new_body}\n{tag_close}"
    new_text, n = pattern.subn(replacement, text, count=1)
    if n == 0:
        new_text = text.rstrip() + f"\n\n{replacement}\n"
    return new_text


def _wrap_md_in_dps(original_text: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    base = _DPS_TEMPLATE.format(ts=ts)
    lines = []
    for line in original_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            lines.append(stripped)
        elif stripped.startswith("-") and stripped[1:].strip():
            lines.append(f"- [ ] {stripped[1:].strip()}")
    next_body = "\n".join(lines) if lines else "# (oryginalna treść poniżej)\n" + original_text[:500]
    return _replace_section(base, "next", next_body)


def _find_cc_executable() -> str | None:
    """Zwraca ścieżkę do polecenia cc (Claude Code CLI)."""
    return shutil.which("cc") or shutil.which("claude")


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color:#3c3c3c;")
    return f


# --------------------------------------------------------------------------- #
# Dialog Wariant A/B/C                                                         #
# --------------------------------------------------------------------------- #

class _PlanChoiceDialog(QDialog):
    """Dialog wyboru działania gdy brak PLAN.md lub plik nie jest DPS."""

    VARIANT_A = "a"
    VARIANT_B = "b"
    VARIANT_C = "c"

    def __init__(
        self,
        project_path: Path | None,
        existing_md: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Zadania — wybierz plik planu")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._project_path = project_path
        self._existing_md = existing_md
        self.chosen_variant = self.VARIANT_C
        self.chosen_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        info_lbl = QLabel(
            "Nie znaleziono pliku PLAN.md w formacie DPS.\n"
            "Wybierz jak chcesz zarządzać zadaniami:"
        )
        info_lbl.setStyleSheet("color:#cccccc;font-size:11px;")
        info_lbl.setWordWrap(True)
        root.addWidget(info_lbl)
        root.addWidget(_sep())

        self._radio_a = QRadioButton("Utwórz nowy PLAN.md (format DPS) w katalogu projektu")
        self._radio_b = QRadioButton("Konwertuj istniejący plik .md do formatu DPS")
        self._radio_c = QRadioButton("Otwórz dowolny plik .md (tryb podglądu, bez DPS)")

        for r in (self._radio_a, self._radio_b, self._radio_c):
            r.setStyleSheet("color:#cccccc;")

        if self._project_path:
            self._radio_a.setChecked(True)
        else:
            self._radio_a.setEnabled(False)
            self._radio_c.setChecked(True)

        if not self._existing_md:
            self._radio_b.setEnabled(False)

        root.addWidget(self._radio_a)
        if self._project_path:
            lbl = QLabel(f"  → {self._project_path / 'PLAN.md'}")
            lbl.setStyleSheet(_LBL_DIM)
            lbl.setFont(_FONT_MONO)
            root.addWidget(lbl)

        root.addWidget(self._radio_b)
        if self._existing_md:
            lbl2 = QLabel(f"  → {self._existing_md}")
            lbl2.setStyleSheet(_LBL_DIM)
            lbl2.setFont(_FONT_MONO)
            root.addWidget(lbl2)

        root.addWidget(self._radio_c)

        root.addWidget(_sep())
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Dalej")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        if self._radio_a.isChecked():
            self.chosen_variant = self.VARIANT_A
            self.chosen_path = self._project_path / "PLAN.md" if self._project_path else None
        elif self._radio_b.isChecked():
            self.chosen_variant = self.VARIANT_B
            self.chosen_path = self._existing_md
        else:
            self.chosen_variant = self.VARIANT_C
            self.chosen_path = None
        self.accept()


# --------------------------------------------------------------------------- #
# Panel AI                                                                      #
# --------------------------------------------------------------------------- #

class _AiPanel(QWidget):
    """Zakładka AI w panelu Zadania — generuje zadania przez cc CLI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._output_buffer: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Tryb AI
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Tryb:", styleSheet=_LBL_KEY))
        self._mode_combo = QComboBox()
        self._mode_combo.setFont(_FONT_SMALL)
        for label, _, _ in _AI_MODES:
            self._mode_combo.addItem(label)
        self._mode_combo.setStyleSheet(
            "QComboBox{background:#1e1e1e;color:#cccccc;border:1px solid #454545;"
            "border-radius:3px;padding:3px 6px;}"
            "QComboBox QAbstractItemView{background:#252526;color:#cccccc;"
            "selection-background-color:#094771;}"
        )
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo, stretch=1)
        root.addLayout(mode_row)

        # Pole opisu od użytkownika
        self._desc_lbl = QLabel("", styleSheet=_LBL_DIM)
        self._desc_lbl.setWordWrap(True)
        root.addWidget(self._desc_lbl)

        self._input_edit = QPlainTextEdit()
        self._input_edit.setFont(_FONT_MONO)
        self._input_edit.setFixedHeight(80)
        self._input_edit.setStyleSheet(
            "QPlainTextEdit{background:#1e1e1e;color:#cccccc;"
            "border:1px solid #454545;border-radius:3px;padding:4px;}"
        )
        root.addWidget(self._input_edit)

        # Przyciski
        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("▶  Uruchom AI")
        self._btn_run.setStyleSheet(_BTN_PURPLE)
        self._btn_run.clicked.connect(self._on_run)
        btn_row.addWidget(self._btn_run)

        self._btn_stop_ai = QPushButton("■  Stop")
        self._btn_stop_ai.setStyleSheet(_BTN_WARN)
        self._btn_stop_ai.clicked.connect(self._on_stop_ai)
        self._btn_stop_ai.setEnabled(False)
        btn_row.addWidget(self._btn_stop_ai)

        self._btn_apply = QPushButton("→ Wstaw do Next")
        self._btn_apply.setStyleSheet(_BTN_GREEN)
        self._btn_apply.clicked.connect(self._on_apply)
        self._btn_apply.setEnabled(False)
        btn_row.addWidget(self._btn_apply)

        btn_row.addStretch()
        self._lbl_ai_status = QLabel("", styleSheet=_LBL_DIM)
        self._lbl_ai_status.setFont(_FONT_SMALL)
        btn_row.addWidget(self._lbl_ai_status)
        root.addLayout(btn_row)

        # Wyjście AI
        out_lbl = QLabel("Odpowiedź AI:", styleSheet=_LBL_KEY)
        root.addWidget(out_lbl)
        self._output_view = QPlainTextEdit()
        self._output_view.setReadOnly(True)
        self._output_view.setFont(_FONT_MONO)
        self._output_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#98c379;"
            "border:1px solid #3c3c3c;border-radius:3px;padding:4px;}"
        )
        root.addWidget(self._output_view, stretch=1)

        self._on_mode_changed(0)

    def _on_mode_changed(self, idx: int) -> None:
        if 0 <= idx < len(_AI_MODES):
            _, hint, _ = _AI_MODES[idx]
            self._desc_lbl.setText(hint)
            self._input_edit.setPlaceholderText(hint)

    def set_plan_context(self, plan_text: str) -> None:
        self._plan_context = plan_text

    def _build_prompt(self) -> str:
        idx = self._mode_combo.currentIndex()
        if idx < 0 or idx >= len(_AI_MODES):
            return ""
        _, _, template = _AI_MODES[idx]
        return template.format(
            plan_context=getattr(self, "_plan_context", "(brak kontekstu)"),
            user_input=self._input_edit.toPlainText().strip() or "(brak)",
        )

    def _on_run(self) -> None:
        cc = _find_cc_executable()
        if not cc:
            QMessageBox.warning(
                self, "Brak cc",
                "Nie znaleziono polecenia 'cc' ani 'claude' w PATH.\n"
                "Zainstaluj Claude Code CLI lub dodaj go do PATH.",
            )
            return

        prompt = self._build_prompt()
        if not prompt:
            return

        self._output_buffer = ""
        self._output_view.clear()
        self._btn_run.setEnabled(False)
        self._btn_stop_ai.setEnabled(True)
        self._btn_apply.setEnabled(False)
        self._lbl_ai_status.setText("Uruchamianie…")

        self._process = QProcess(self)
        self._process.setProgram(cc)
        self._process.setArguments(["-p", prompt, "--output-format", "stream-json", "--no-cwd"])
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start()

        if not self._process.waitForStarted(3000):
            self._lbl_ai_status.setText("Błąd startu procesu")
            self._btn_run.setEnabled(True)
            self._btn_stop_ai.setEnabled(False)

    def _on_stdout(self) -> None:
        if not self._process:
            return
        raw = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        # stream-json: każda linia to JSON z polem "type" i "content"
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # format stream-json: {type: "content_block_delta", delta: {text: "..."}}
                # lub uproszczony: {type: "text", text: "..."}
                chunk = ""
                if obj.get("type") == "content_block_delta":
                    chunk = obj.get("delta", {}).get("text", "")
                elif obj.get("type") == "text":
                    chunk = obj.get("text", "")
                elif obj.get("type") == "result":
                    chunk = obj.get("result", "")
                if chunk:
                    self._output_buffer += chunk
                    self._output_view.moveCursor(QTextCursor.MoveOperation.End)
                    self._output_view.insertPlainText(chunk)
            except (json.JSONDecodeError, KeyError):
                # Nie-JSON fallback — wyświetl wprost
                self._output_buffer += line + "\n"
                self._output_view.moveCursor(QTextCursor.MoveOperation.End)
                self._output_view.insertPlainText(line + "\n")

    def _on_stderr(self) -> None:
        if not self._process:
            return
        raw = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if raw.strip():
            self._output_view.moveCursor(QTextCursor.MoveOperation.End)
            self._output_view.insertPlainText(f"\n[STDERR] {raw}")

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self._btn_run.setEnabled(True)
        self._btn_stop_ai.setEnabled(False)
        has_output = bool(self._output_buffer.strip())
        self._btn_apply.setEnabled(has_output)
        if exit_code == 0:
            self._lbl_ai_status.setText("Gotowe")
        else:
            self._lbl_ai_status.setText(f"Zakończono (kod {exit_code})")

    def _on_stop_ai(self) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._lbl_ai_status.setText("Przerwano")
        self._btn_run.setEnabled(True)
        self._btn_stop_ai.setEnabled(False)

    def _on_apply(self) -> None:
        """Emitujemy sygnał do rodzica przez callback — unikamy dziedziczenia sygnałów."""
        if self._apply_callback:
            self._apply_callback(self._output_buffer)

    def set_apply_callback(self, fn) -> None:
        self._apply_callback = fn

    _apply_callback = None


# --------------------------------------------------------------------------- #
# Główny panel                                                                  #
# --------------------------------------------------------------------------- #

class ZadaniaPanel(QWidget):
    """Panel Zadania — otwiera plik PLAN.md (DPS lub zwykły) i zarządza sekcją next."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plan_path: Path | None = None
        self._plan_text: str = ""
        self._is_dps: bool = False
        self._setup_ui()

    # ------------------------------------------------------------------ #
    # Budowanie UI                                                          #
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Nagłówek
        hdr = QHBoxLayout()
        title = QLabel("Zadania — PLAN.md")
        title.setStyleSheet("color:#cccccc;font-size:13px;font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._lbl_badge = QLabel("")
        self._lbl_badge.setStyleSheet(
            "background:#1a3a1a;color:#98c379;border-radius:3px;"
            "padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        self._lbl_badge.setVisible(False)
        hdr.addWidget(self._lbl_badge)
        root.addLayout(hdr)

        root.addWidget(_sep())

        # Pasek ścieżki
        path_row = QHBoxLayout()
        self._lbl_path = QLabel("(brak planu — użyj przycisku lub otwórz projekt w Sesje CC)")
        self._lbl_path.setFont(_FONT_MONO)
        self._lbl_path.setStyleSheet(_LBL_DIM)
        self._lbl_path.setWordWrap(True)
        path_row.addWidget(self._lbl_path, stretch=1)

        self._btn_open = QPushButton("Otwórz…")
        self._btn_open.setStyleSheet(_BTN)
        self._btn_open.clicked.connect(self._on_open_manual)
        path_row.addWidget(self._btn_open)

        self._btn_reload = QPushButton("⟳")
        self._btn_reload.setFixedWidth(32)
        self._btn_reload.setStyleSheet(_BTN)
        self._btn_reload.clicked.connect(self._reload)
        self._btn_reload.setEnabled(False)
        path_row.addWidget(self._btn_reload)
        root.addLayout(path_row)

        # Splitter pionowy: góra = meta/current, dół = zakładki (Next | AI)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # -- Górna: Meta + Current (scrollowana)
        top_scroll = QScrollArea()
        top_scroll.setWidgetResizable(True)
        top_scroll.setFrameShape(QFrame.Shape.NoFrame)
        top_inner = QWidget()
        top_lay = QVBoxLayout(top_inner)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(6)

        meta_card = QFrame()
        meta_card.setStyleSheet(_CARD)
        meta_cl = QVBoxLayout(meta_card)
        meta_cl.setContentsMargins(8, 6, 8, 6)
        meta_cl.setSpacing(2)
        meta_cl.addWidget(QLabel("Stan planu", styleSheet=_LBL_HEAD))
        self._lbl_status = QLabel("—", styleSheet=_LBL_VAL)
        self._lbl_goal = QLabel("—", styleSheet=_LBL_VAL, wordWrap=True)
        self._lbl_session = QLabel("—", styleSheet=_LBL_DIM)
        for key, lbl in [
            ("Status:", self._lbl_status),
            ("Cel:", self._lbl_goal),
            ("Sesja:", self._lbl_session),
        ]:
            row = QHBoxLayout()
            k = QLabel(key, styleSheet=_LBL_KEY)
            k.setFixedWidth(60)
            row.addWidget(k)
            row.addWidget(lbl, stretch=1)
            meta_cl.addLayout(row)
        top_lay.addWidget(meta_card)

        cur_card = QFrame()
        cur_card.setStyleSheet(_CARD)
        cur_cl = QVBoxLayout(cur_card)
        cur_cl.setContentsMargins(8, 6, 8, 6)
        cur_cl.setSpacing(2)
        cur_cl.addWidget(QLabel("Aktywne zadanie", styleSheet=_LBL_HEAD))
        self._lbl_cur_task = QLabel("—", styleSheet=_LBL_VAL, wordWrap=True)
        self._lbl_cur_task.setFont(_FONT_MONO)
        cur_cl.addWidget(self._lbl_cur_task)
        top_lay.addWidget(cur_card)

        top_lay.addStretch()
        top_scroll.setWidget(top_inner)
        splitter.addWidget(top_scroll)

        # -- Dolna: zakładki Next i AI
        bottom_tabs = QTabWidget()
        bottom_tabs.setDocumentMode(True)
        bottom_tabs.setStyleSheet(
            "QTabBar::tab{background:#2d2d2d;color:#aaaaaa;padding:4px 12px;"
            "border:none;margin-right:2px;border-radius:3px 3px 0 0;}"
            "QTabBar::tab:selected{background:#007acc;color:#ffffff;}"
            "QTabBar::tab:hover:!selected{background:#3c3c3c;color:#cccccc;}"
        )

        # Zakładka Next
        next_w = self._build_next_tab()
        bottom_tabs.addTab(next_w, "Next")

        # Zakładka AI
        self._ai_panel = _AiPanel()
        self._ai_panel.set_apply_callback(self._on_ai_apply)
        bottom_tabs.addTab(self._ai_panel, "✦ AI")

        splitter.addWidget(bottom_tabs)
        splitter.setSizes([180, 400])
        root.addWidget(splitter, stretch=1)

    def _build_next_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4)

        next_hdr = QHBoxLayout()
        next_hdr.addWidget(QLabel("Następne zadania (SECTION:next)", styleSheet=_LBL_HEAD))
        next_hdr.addStretch()
        self._btn_save = QPushButton("Zapisz")
        self._btn_save.setStyleSheet(_BTN_ACCENT)
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save_next)
        next_hdr.addWidget(self._btn_save)
        lay.addLayout(next_hdr)

        self._next_editor = QPlainTextEdit()
        self._next_editor.setFont(_FONT_MONO)
        self._next_editor.setPlaceholderText("- [ ] Zadanie 1\n- [ ] Zadanie 2\n...")
        self._next_editor.textChanged.connect(lambda: self._btn_save.setEnabled(True))
        lay.addWidget(self._next_editor, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(6)

        self._btn_add_task = QPushButton("+ Dodaj zadanie")
        self._btn_add_task.setStyleSheet(_BTN_GREEN)
        self._btn_add_task.clicked.connect(self._on_add_task)
        self._btn_add_task.setEnabled(False)
        actions.addWidget(self._btn_add_task)

        self._btn_archive = QPushButton("Oczyszczenie → ARCHIWUM.md")
        self._btn_archive.setStyleSheet(_BTN_WARN)
        self._btn_archive.clicked.connect(self._on_archive)
        self._btn_archive.setEnabled(False)
        actions.addWidget(self._btn_archive)

        actions.addStretch()
        self._lbl_hint = QLabel("")
        self._lbl_hint.setStyleSheet(_LBL_DIM)
        self._lbl_hint.setFont(_FONT_SMALL)
        actions.addWidget(self._lbl_hint)
        lay.addLayout(actions)

        return w

    # ------------------------------------------------------------------ #
    # Publiczne API                                                         #
    # ------------------------------------------------------------------ #

    def load_from_project(self, project_path: str | Path, silent: bool = False) -> None:
        """Wczytaj projekt. Gdy silent=True — nie pokazuj żadnych dialogów.

        Wariant A (DPS) — ładuje od razu.
        Wariant B/C — gdy silent=True tylko informuje etykietą; dialog pojawia
        się dopiero gdy użytkownik kliknie 'Otwórz…' lub wywoła bez silent.
        """
        project_path = Path(project_path)
        plan_path = project_path / "PLAN.md"

        if plan_path.exists():
            try:
                text = plan_path.read_text(encoding="utf-8")
            except OSError:
                text = ""

            if _is_dps(text):
                self._apply_file(plan_path, text)
                return

            if silent:
                self._lbl_path.setText(f"{plan_path}  (nie DPS — kliknij Otwórz…)")
                self._lbl_path.setStyleSheet(_LBL_WARN)
                return

            dlg = _PlanChoiceDialog(project_path=project_path, existing_md=plan_path, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self._handle_choice(dlg, project_path, original_text=text)
        else:
            if silent:
                self._lbl_path.setText(f"Brak PLAN.md w {project_path}  — kliknij Otwórz…")
                self._lbl_path.setStyleSheet(_LBL_WARN)
                return

            dlg = _PlanChoiceDialog(project_path=project_path, existing_md=None, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self._handle_choice(dlg, project_path, original_text="")

    # ------------------------------------------------------------------ #
    # Logika wewnętrzna                                                     #
    # ------------------------------------------------------------------ #

    def _handle_choice(self, dlg: _PlanChoiceDialog, project_path: Path, original_text: str) -> None:
        variant = dlg.chosen_variant
        chosen_path = dlg.chosen_path

        if variant == _PlanChoiceDialog.VARIANT_A:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_text = _DPS_TEMPLATE.format(ts=ts)
            target = project_path / "PLAN.md"
            try:
                target.write_text(new_text, encoding="utf-8")
            except OSError as e:
                QMessageBox.critical(self, "Błąd", f"Nie można zapisać:\n{e}")
                return
            self._apply_file(target, new_text)

        elif variant == _PlanChoiceDialog.VARIANT_B:
            if not chosen_path or not chosen_path.exists():
                return
            src_text = original_text or chosen_path.read_text(encoding="utf-8")
            new_text = _wrap_md_in_dps(src_text)
            reply = QMessageBox.question(
                self, "Konwersja do DPS",
                f"Plik zostanie nadpisany formatem DPS:\n{chosen_path}\n\nKontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                chosen_path.write_text(new_text, encoding="utf-8")
            except OSError as e:
                QMessageBox.critical(self, "Błąd", f"Nie można zapisać:\n{e}")
                return
            self._apply_file(chosen_path, new_text)

        else:
            start = str(project_path) if project_path.is_dir() else str(Path.home())
            path, _ = QFileDialog.getOpenFileName(
                self, "Wybierz plik .md", start, "Markdown (*.md);;Wszystkie pliki (*)",
            )
            if not path:
                return
            try:
                text = Path(path).read_text(encoding="utf-8")
            except OSError as e:
                QMessageBox.critical(self, "Błąd", str(e))
                return
            self._apply_file(Path(path), text)

    def _on_open_manual(self) -> None:
        start = str(self._plan_path.parent) if self._plan_path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz plik .md", start, "Markdown (*.md);;Wszystkie pliki (*)",
        )
        if not path:
            return
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Błąd", str(e))
            return

        if not _is_dps(text):
            reply = QMessageBox.question(
                self, "Format DPS",
                "Plik nie jest w formacie DPS.\nKonwertować do DPS?\n(Nie — otwórz w trybie zwykłym)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                new_text = _wrap_md_in_dps(text)
                if QMessageBox.question(
                    self, "Zapis", f"Nadpisać plik?\n{p}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes:
                    try:
                        p.write_text(new_text, encoding="utf-8")
                    except OSError as e:
                        QMessageBox.critical(self, "Błąd zapisu", str(e))
                        return
                    text = new_text
        self._apply_file(p, text)

    def _reload(self) -> None:
        if self._plan_path:
            try:
                text = self._plan_path.read_text(encoding="utf-8")
            except OSError:
                return
            self._apply_file(self._plan_path, text)

    def _apply_file(self, path: Path, text: str) -> None:
        self._plan_path = path
        self._plan_text = text
        self._is_dps = _is_dps(text)

        self._lbl_path.setText(str(path))
        self._lbl_badge.setVisible(self._is_dps)
        self._lbl_badge.setText("DPS" if self._is_dps else "")

        self._btn_reload.setEnabled(True)
        self._btn_add_task.setEnabled(True)
        self._btn_archive.setEnabled(self._is_dps)

        # Przekaż kontekst do panelu AI
        self._ai_panel.set_plan_context(text)

        self._render()
        self._btn_save.setEnabled(False)
        self._lbl_hint.setText(f"{'DPS' if self._is_dps else 'Zwykły MD'} · {path.name}")

    def _render(self) -> None:
        text = self._plan_text
        if self._is_dps:
            meta_raw = _read_section(text, "meta")
            meta: dict[str, str] = {}
            for line in meta_raw.splitlines():
                if line.startswith("-") and ":" in line:
                    k, _, v = line[1:].partition(":")
                    meta[k.strip()] = v.strip()

            status = meta.get("status", "—")
            if status == "active":
                self._lbl_status.setText("● active")
                self._lbl_status.setStyleSheet("color:#98c379;font-size:10px;font-weight:bold;")
            elif status == "idle":
                self._lbl_status.setText("◌ idle")
                self._lbl_status.setStyleSheet("color:#5c6370;font-size:10px;font-weight:bold;")
            else:
                self._lbl_status.setText(status or "—")
                self._lbl_status.setStyleSheet(_LBL_VAL)

            self._lbl_goal.setText(meta.get("goal", "—") or "—")
            self._lbl_session.setText(
                f"Sesja {meta.get('session', '—')} · {meta.get('updated', '—')}"
            )

            cur_raw = _read_section(text, "current")
            cur: dict[str, str] = {}
            for line in cur_raw.splitlines():
                if line.startswith("-") and ":" in line:
                    k, _, v = line[1:].partition(":")
                    cur[k.strip()] = v.strip()
            self._lbl_cur_task.setText(cur.get("task", "") or "(brak aktywnego zadania)")

            next_body = _read_section(text, "next")
            self._next_editor.blockSignals(True)
            self._next_editor.setPlainText(next_body)
            self._next_editor.blockSignals(False)
        else:
            self._lbl_status.setText("(zwykły plik MD)")
            self._lbl_status.setStyleSheet(_LBL_DIM)
            self._lbl_goal.setText(str(self._plan_path))
            self._lbl_session.setText("")
            self._lbl_cur_task.setText("(brak sekcji DPS)")
            self._next_editor.blockSignals(True)
            self._next_editor.setPlainText(self._plan_text)
            self._next_editor.blockSignals(False)

    def _on_save_next(self) -> None:
        if not self._plan_path:
            return
        new_body = self._next_editor.toPlainText()
        if self._is_dps:
            new_text = _replace_section(self._plan_text, "next", new_body)
        else:
            new_text = new_body
        try:
            self._plan_path.write_text(new_text, encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return
        self._plan_text = new_text
        self._btn_save.setEnabled(False)
        self._lbl_hint.setText(f"Zapisano · {self._plan_path.name}")

    def _on_add_task(self) -> None:
        text = self._next_editor.toPlainText()
        insert = "- [ ] "
        if text and not text.endswith("\n"):
            insert = "\n" + insert
        self._next_editor.moveCursor(QTextCursor.MoveOperation.End)
        self._next_editor.insertPlainText(insert)
        self._next_editor.setFocus()

    def _on_archive(self) -> None:
        if not self._plan_path or not self._is_dps:
            return
        done_body = _read_section(self._plan_text, "done")
        done_items = [l.strip() for l in done_body.splitlines() if l.strip()]
        if not done_items:
            QMessageBox.information(self, "Oczyszczenie", "Sekcja Done jest pusta.")
            return

        archiwum_path = self._plan_path.parent / "ARCHIWUM.md"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with archiwum_path.open("a", encoding="utf-8") as f:
                f.write(f"\n## Archiwum {ts}\n" + "\n".join(done_items) + "\n")
        except OSError as e:
            QMessageBox.critical(self, "Błąd archiwizacji", str(e))
            return

        new_text = _replace_section(self._plan_text, "done", "")
        try:
            self._plan_path.write_text(new_text, encoding="utf-8")
        except OSError as e:
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return
        self._plan_text = new_text
        self._render()
        self._btn_save.setEnabled(False)
        QMessageBox.information(
            self, "Oczyszczenie",
            f"Zarchiwizowano {len(done_items)} zadań do:\n{archiwum_path}",
        )

    def _on_ai_apply(self, ai_output: str) -> None:
        """Wstawia wygenerowane przez AI zadania do edytora Next."""
        lines = []
        for line in ai_output.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                lines.append(stripped)
            elif stripped.startswith("- ") and stripped[2:].strip():
                lines.append(f"- [ ] {stripped[2:].strip()}")

        if not lines:
            # Brak listy — wstaw cały output jako komentarz
            lines = [f"# {l}" for l in ai_output.strip().splitlines() if l.strip()]

        current = self._next_editor.toPlainText().rstrip()
        new_content = (current + "\n" if current else "") + "\n".join(lines)
        self._next_editor.setPlainText(new_content)
        self._btn_save.setEnabled(True)
        self._lbl_hint.setText("AI → wstawiono do Next (zapisz, żeby zachować)")
