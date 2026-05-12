"""Panel 'Prompt Score' — podgląd PS.md projektu SSS v3 (prompt, pytania, oceny, porady sędziów)."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
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

_BTN_WARN = (
    "QPushButton{background:#2d2000;color:#e5c07b;border:1px solid #6b5a00;"
    "border-radius:3px;padding:4px 12px}"
    "QPushButton:hover{background:#3d2d00}"
    "QPushButton:disabled{color:#5c5c5c;border-color:#383838}"
)

_CARD = "QFrame{background:#1e1e1e;border:1px solid #3c3c3c;border-radius:4px;}"

_LBL_DIM = "color:#5c6370;font-size:10px;"
_LBL_KEY = "color:#9cdcfe;font-size:10px;"
_LBL_VAL = "color:#cccccc;font-size:10px;"
_LBL_OK = "color:#98c379;font-size:10px;"
_LBL_WARN = "color:#e5c07b;font-size:10px;"
_LBL_ERR = "color:#e06c75;font-size:10px;"

_RE_SECTION = re.compile(
    r"<!--\s*SECTION:(\w+)\s*-->(.*?)<!--\s*/SECTION:\1\s*-->", re.DOTALL
)

_JUDGE_COLORS: dict[str, str] = {
    "judge-business": "#e5c07b",
    "judge-architect": "#61afef",
    "judge-pm": "#98c379",
    "judge-devops": "#56b6c2",
    "judge-devil": "#e06c75",
    "aggregate": "#c678dd",
}

_JUDGE_LABELS: dict[str, str] = {
    "judge-business": "Business",
    "judge-architect": "Architect",
    "judge-pm": "PM",
    "judge-devops": "DevOps",
    "judge-devil": "Devil's Advocate",
    "aggregate": "Agregat",
}

_JUDGE_ORDER = ["judge-business", "judge-architect", "judge-pm", "judge-devops", "judge-devil"]

# --------------------------------------------------------------------------- #
# Parsery                                                                       #
# --------------------------------------------------------------------------- #

def _read_section(text: str, name: str) -> str:
    for m in _RE_SECTION.finditer(text):
        if m.group(1).lower() == name.lower():
            return m.group(2).strip()
    return ""


def _parse_meta(section_text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in section_text.splitlines():
        line = line.strip()
        if line.startswith("- ") and ":" in line:
            k, _, v = line[2:].partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _parse_judges(section_text: str) -> list[dict[str, str]]:
    judges: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in section_text.splitlines():
        line = line.strip()
        if line.startswith("### "):
            if current:
                judges.append(current)
            current = {"name": line[4:].strip()}
        elif line.startswith("- ") and ":" in line:
            k, _, v = line[2:].partition(":")
            current[k.strip()] = v.strip()
    if current:
        judges.append(current)
    return judges


def _parse_round(section_text: str) -> list[dict[str, str]]:
    """Parser pytań SSS v3: obsługuje zagnieżdżone - A: i - source_judge: oraz - proposals_log:"""
    questions: list[dict[str, str]] = []
    current: dict[str, str] = {}
    proposals_log: str = ""

    for line in section_text.splitlines():
        # proposals_log to pole na poziomie sekcji, nie pytania
        if re.match(r"^- proposals_log:", line):
            _, _, v = line.partition(":")
            proposals_log = v.strip()
            continue

        # Nowe pytanie: "- Q1: tekst" lub zagnieżdżone "  - Q1: tekst"
        m = re.match(r"^-?\s*- Q(\d+):\s*(.*)", line)
        if not m:
            m = re.match(r"^- Q(\d+):\s*(.*)", line)
        if m:
            if current and "q" in current:
                questions.append(current)
            current = {"q": m.group(2).strip(), "num": m.group(1)}
            continue

        # Zagnieżdżone pola: "  - A:", "  - source_judge:", "  - A: tekst"
        stripped = line.strip()
        if stripped.startswith("- A:"):
            current["a"] = stripped[4:].strip()
        elif stripped.startswith("- source_judge:"):
            current["source"] = stripped[15:].strip()

    if current and "q" in current:
        questions.append(current)

    # Dołącz proposals_log jako ostatni element jeśli istnieje
    if proposals_log and proposals_log not in ("-", "—", ""):
        for q in questions:
            q.setdefault("proposals_log", proposals_log)

    return questions


def _is_empty(value: str) -> bool:
    return not value or value.strip() in ("-", "—", "")


# --------------------------------------------------------------------------- #
# Migrator PS.md v2 → v3                                                       #
# --------------------------------------------------------------------------- #

def _detect_ps_version(text: str) -> str:
    """Zwraca 'v3' jeśli plik ma cechy v3, 'v2' jeśli stary format."""
    if "proposals_log" in text:
        return "v3"
    if "Round 1 (statyczna" in text or "Round 2 (panel" in text:
        return "v3"
    if "- status:" in text:
        return "v3"
    return "v2"


_V3_ROUND_TEMPLATE = """\
### Round {num} {desc}
- Q1: -
  - {extra}A: -
- Q2: -
  - {extra}A: -
- Q3: -
  - {extra}A: -
{proposals}"""


def _migrate_v2_to_v3(text: str) -> str:
    """
    Migruje PS.md v2 do formatu v3:
    - Dodaje pole 'status' do meta jeśli brak
    - Przepisuje round_1/round_2/round_3 do nowego formatu
    - Dodaje proposals_log do round_2 i round_3
    - Zachowuje istniejące dane
    """
    result = text

    # 1. Dodaj status do meta jeśli brak
    meta_section = _read_section(text, "meta")
    if meta_section and "- status:" not in meta_section:
        old_meta_block = f"<!-- SECTION:meta -->\n{meta_section}\n<!-- /SECTION:meta -->"
        new_meta_content = meta_section.rstrip() + "\n- status: -"
        new_meta_block = f"<!-- SECTION:meta -->\n{new_meta_content}\n<!-- /SECTION:meta -->"
        result = result.replace(old_meta_block, new_meta_block)

    # 2. Przepisz rundy — dodaj nagłówki sekcji jeśli brak
    for section_name, desc, has_source, has_proposals in [
        ("round_1", "(statyczna, główny Claude)", False, False),
        ("round_2", "(panel sędziów → orchestrator wybiera 3 z 15)", True, True),
        ("round_3", "(panel sędziów → orchestrator wybiera 3 z 15)", True, True),
    ]:
        section_text = _read_section(result, section_name)
        if not section_text:
            # Brak sekcji — nie dodajemy, zostawiamy jak jest
            continue

        round_num = section_name.split("_")[1]
        has_v3_header = f"Round {round_num}" in section_text

        if not has_v3_header:
            # Stara sekcja — przepisz do nowego formatu, zachowując dane
            old_questions = _parse_round(section_text)
            lines = [f"### Round {round_num} {desc}"]
            for i, q in enumerate(old_questions, 1):
                q_text = q.get("q", "-") or "-"
                lines.append(f"- Q{i}: {q_text}")
                if has_source:
                    src = q.get("source", "-") or "-"
                    lines.append(f"  - source_judge: {src}")
                a_text = q.get("a", "-") or "-"
                lines.append(f"  - A: {a_text}")
            if has_proposals:
                lines.append("- proposals_log: -")

            new_content = "\n".join(lines)
            old_block = f"<!-- SECTION:{section_name} -->\n{section_text}\n<!-- /SECTION:{section_name} -->"
            new_block = f"<!-- SECTION:{section_name} -->\n{new_content}\n<!-- /SECTION:{section_name} -->"
            result = result.replace(old_block, new_block)

        elif has_proposals and "proposals_log" not in section_text:
            # Sekcja ma v3 nagłówek ale brak proposals_log — dodaj
            old_block = f"<!-- SECTION:{section_name} -->\n{section_text}\n<!-- /SECTION:{section_name} -->"
            new_content = section_text.rstrip() + "\n- proposals_log: -"
            new_block = f"<!-- SECTION:{section_name} -->\n{new_content}\n<!-- /SECTION:{section_name} -->"
            result = result.replace(old_block, new_block)

    return result


# --------------------------------------------------------------------------- #
# Pomocnicy UI                                                                  #
# --------------------------------------------------------------------------- #

def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color:#3c3c3c;")
    return f


def _make_scroll() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea{border:none;background:#141414;}"
        "QScrollBar:vertical{background:#1e1e1e;width:8px;border-radius:4px;}"
        "QScrollBar::handle:vertical{background:#454545;border-radius:4px;}"
    )
    container = QWidget()
    container.setStyleSheet("background:#141414;")
    lay = QVBoxLayout(container)
    lay.setContentsMargins(8, 8, 8, 8)
    lay.setSpacing(6)
    lay.addStretch()
    scroll.setWidget(container)
    return scroll, lay


def _insert(lay: QVBoxLayout, widget: QWidget) -> None:
    """Wstawia widget przed końcowym stretch."""
    lay.insertWidget(lay.count() - 1, widget)


def _insert_layout(lay: QVBoxLayout, inner: QHBoxLayout) -> None:
    lay.insertLayout(lay.count() - 1, inner)


def _clear_content(lay: QVBoxLayout) -> None:
    """Usuwa wszystkie widgety z layoutu zostawiając końcowy stretch."""
    while lay.count() > 1:
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def _section_label(text: str, color: str = "#9cdcfe") -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{color};font-size:11px;font-weight:bold;background:transparent;"
    )
    return lbl


# --------------------------------------------------------------------------- #
# Dialog podglądu migracji                                                      #
# --------------------------------------------------------------------------- #

class _MigratePreviewDialog(QDialog):
    def __init__(self, original: str, migrated: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Podgląd migracji PS.md v2 → v3")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background:#141414;color:#cccccc;")

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        info = QLabel(
            "Poniżej widoczny wynik migracji PS.md do formatu SSS v3. "
            "Sprawdź zmiany i kliknij <b>Zapisz</b> aby nadpisać plik."
        )
        info.setStyleSheet("color:#9cdcfe;font-size:10px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        cols = QHBoxLayout()

        for title, content in [("Oryginał (v2)", original), ("Po migracji (v3)", migrated)]:
            col = QVBoxLayout()
            lbl = QLabel(title)
            lbl.setStyleSheet("color:#5c6370;font-size:10px;font-weight:bold;")
            col.addWidget(lbl)
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setFont(_FONT_MONO)
            view.setPlainText(content)
            view.setStyleSheet(
                "QPlainTextEdit{background:#0d1117;color:#cccccc;"
                "border:1px solid #3c3c3c;border-radius:4px;padding:6px;}"
            )
            col.addWidget(view)
            cols.addLayout(col)

        lay.addLayout(cols, stretch=1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet(
            "QPushButton{background:#2d2d2d;color:#cccccc;border:1px solid #454545;"
            "border-radius:3px;padding:4px 14px}"
            "QPushButton:hover{background:#3c3c3c}"
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)


# --------------------------------------------------------------------------- #
# Główny panel                                                                  #
# --------------------------------------------------------------------------- #

class PromptScorePanel(QWidget):
    """Panel Prompt Score — wyświetla dane z PS.md projektu SSS v3."""

    _DEFAULT_COLOR = "#9d9d9d"

    def __init__(self, parent: QWidget | None = None, slot_color: str = "") -> None:
        super().__init__(parent)
        self._ps_path: Path | None = None
        self._ps_text: str = ""
        self._slot_color: str = slot_color or self._DEFAULT_COLOR
        self._setup_ui()

    # ------------------------------------------------------------------ #
    # Budowanie UI                                                          #
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        # Nagłówek
        hdr = QHBoxLayout()
        title = QLabel("Prompt Score")
        title.setStyleSheet("color:#cccccc;font-size:13px;font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._lbl_version = QLabel("")
        self._lbl_version.setStyleSheet(
            "background:#1a2a1a;color:#98c379;border-radius:3px;"
            "padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        self._lbl_version.setVisible(False)
        hdr.addWidget(self._lbl_version)

        self._btn_migrate = QPushButton("Dostosuj →v3")
        self._btn_migrate.setStyleSheet(_BTN_WARN)
        self._btn_migrate.setToolTip("Dostosuj PS.md do formatu SSS v3")
        self._btn_migrate.setVisible(False)
        self._btn_migrate.clicked.connect(self._on_migrate)
        hdr.addWidget(self._btn_migrate)

        self._lbl_badge = QLabel("PS.md")
        self._lbl_badge.setStyleSheet(
            "background:#1a2a3a;color:#61afef;border-radius:3px;"
            "padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        self._lbl_badge.setVisible(False)
        hdr.addWidget(self._lbl_badge)
        root.addLayout(hdr)

        # Pasek ścieżki
        path_row = QHBoxLayout()
        self._lbl_path = QLabel("(brak projektu — wybierz slot z PS.md)")
        self._lbl_path.setFont(_FONT_MONO)
        self._lbl_path.setStyleSheet(_LBL_DIM)
        self._lbl_path.setWordWrap(True)
        path_row.addWidget(self._lbl_path, stretch=1)

        self._btn_reload = QPushButton("⟳")
        self._btn_reload.setFixedWidth(32)
        self._btn_reload.setStyleSheet(_BTN)
        self._btn_reload.setEnabled(False)
        self._btn_reload.clicked.connect(self._reload)
        path_row.addWidget(self._btn_reload)
        root.addLayout(path_row)

        root.addWidget(_sep())

        # Zakładki
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._apply_tab_style()

        self._tabs.addTab(self._build_prompt_tab(), "Prompt")
        self._tabs.addTab(self._build_pytania_tab(), "Pytania")
        self._tabs.addTab(self._build_oceny_tab(), "Oceny")
        self._tabs.addTab(self._build_porady_tab(), "Porady sędziów")

        root.addWidget(self._tabs, stretch=1)

    def _apply_tab_style(self) -> None:
        c = self._slot_color
        self._tabs.setStyleSheet(
            "QTabWidget::pane{border:none;background:#141414;}"
            f"QTabBar::tab{{background:#1a1a1a;color:#5c6370;"
            f"font-size:10px;padding:5px 14px;border:none;margin-right:2px;}}"
            f"QTabBar::tab:selected{{background:#1e1e1e;color:{c};"
            f"border-bottom:2px solid {c};}}"
            "QTabBar::tab:hover:!selected{background:#222222;color:#9d9d9d;}"
        )

    def set_slot_color(self, color: str) -> None:
        """Aktualizuje kolor akcentu zakładek zgodnie z kolorem slotu."""
        self._slot_color = color or self._DEFAULT_COLOR
        self._apply_tab_style()

    # -- Budowanie zakładek ------------------------------------------------

    def _build_prompt_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:#141414;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # Karta meta
        meta_frame = QFrame()
        meta_frame.setStyleSheet(_CARD)
        meta_lay = QHBoxLayout(meta_frame)
        meta_lay.setContentsMargins(10, 6, 10, 6)
        meta_lay.setSpacing(0)

        self._lbl_project = QLabel("—")
        self._lbl_project.setStyleSheet("color:#9cdcfe;font-size:10px;font-weight:bold;")
        self._lbl_created = QLabel("—")
        self._lbl_created.setStyleSheet(_LBL_DIM)
        self._lbl_prompt_len = QLabel("—")
        self._lbl_prompt_len.setStyleSheet(_LBL_VAL)
        self._lbl_ps_status = QLabel("—")
        self._lbl_ps_status.setStyleSheet(_LBL_DIM)

        for key, lbl in [
            ("Projekt:", self._lbl_project),
            ("Utworzony:", self._lbl_created),
            ("Długość:", self._lbl_prompt_len),
            ("Status:", self._lbl_ps_status),
        ]:
            meta_lay.addWidget(QLabel(key, styleSheet=_LBL_KEY))
            meta_lay.addSpacing(4)
            meta_lay.addWidget(lbl)
            meta_lay.addSpacing(20)
        meta_lay.addStretch()
        lay.addWidget(meta_frame)

        # Treść promptu
        lbl = QLabel("Treść promptu:", styleSheet=_LBL_KEY)
        lay.addWidget(lbl)

        self._prompt_view = QPlainTextEdit()
        self._prompt_view.setReadOnly(True)
        self._prompt_view.setFont(_FONT_MONO)
        self._prompt_view.setPlaceholderText(
            "Brak danych — załaduj projekt z plikiem PS.md"
        )
        self._prompt_view.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#cccccc;"
            "border:1px solid #3c3c3c;border-radius:4px;padding:8px;}"
        )
        lay.addWidget(self._prompt_view, stretch=1)
        return w

    def _build_pytania_tab(self) -> QWidget:
        self._pytania_scroll, self._pytania_lay = _make_scroll()
        return self._pytania_scroll

    def _build_oceny_tab(self) -> QWidget:
        self._oceny_scroll, self._oceny_lay = _make_scroll()
        return self._oceny_scroll

    def _build_porady_tab(self) -> QWidget:
        self._porady_scroll, self._porady_lay = _make_scroll()
        return self._porady_scroll

    # ------------------------------------------------------------------ #
    # Publiczne API                                                         #
    # ------------------------------------------------------------------ #

    def load_from_project(self, project_path: str | Path, silent: bool = False) -> None:
        project_path = Path(project_path)
        ps_path = project_path / "PS.md"

        if not ps_path.exists():
            self._lbl_path.setText(f"Brak PS.md w {project_path}")
            self._lbl_path.setStyleSheet(_LBL_DIM)
            self._lbl_badge.setVisible(False)
            self._lbl_version.setVisible(False)
            self._btn_migrate.setVisible(False)
            self._btn_reload.setEnabled(False)
            self._clear_all()
            return

        try:
            text = ps_path.read_text(encoding="utf-8")
        except OSError as e:
            self._lbl_path.setText(f"Błąd odczytu: {e}")
            self._lbl_path.setStyleSheet(_LBL_ERR)
            return

        self._ps_path = ps_path
        self._ps_text = text
        self._lbl_path.setText(str(ps_path))
        self._lbl_path.setStyleSheet(_LBL_VAL)
        self._lbl_badge.setVisible(True)
        self._btn_reload.setEnabled(True)

        version = _detect_ps_version(text)
        self._lbl_version.setText(version)
        self._lbl_version.setStyleSheet(
            f"background:{'#1a2a1a' if version == 'v3' else '#2a1a00'};"
            f"color:{'#98c379' if version == 'v3' else '#e5c07b'};"
            "border-radius:3px;padding:2px 8px;font-size:10px;font-weight:bold;"
        )
        self._lbl_version.setVisible(True)
        self._btn_migrate.setVisible(version != "v3")

        self._render()

    # ------------------------------------------------------------------ #
    # Logika wewnętrzna                                                     #
    # ------------------------------------------------------------------ #

    def _reload(self) -> None:
        if not self._ps_path:
            return
        try:
            self._ps_text = self._ps_path.read_text(encoding="utf-8")
        except OSError:
            return
        version = _detect_ps_version(self._ps_text)
        self._lbl_version.setText(version)
        self._btn_migrate.setVisible(version != "v3")
        self._render()

    def _clear_all(self) -> None:
        self._prompt_view.setPlainText("")
        self._lbl_project.setText("—")
        self._lbl_created.setText("—")
        self._lbl_prompt_len.setText("—")
        self._lbl_ps_status.setText("—")
        _clear_content(self._pytania_lay)
        _clear_content(self._oceny_lay)
        _clear_content(self._porady_lay)

    def _render(self) -> None:
        text = self._ps_text
        self._render_prompt_tab(text)
        self._render_pytania_tab(text)
        self._render_oceny_tab(text)
        self._render_porady_tab(text)

    def _on_migrate(self) -> None:
        if not self._ps_path or not self._ps_text:
            return
        migrated = _migrate_v2_to_v3(self._ps_text)
        if migrated == self._ps_text:
            QMessageBox.information(
                self, "Brak zmian",
                "Plik PS.md nie wymaga migracji lub nie można automatycznie\n"
                "wykryć różnic między wersjami."
            )
            return
        dlg = _MigratePreviewDialog(self._ps_text, migrated, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._ps_path.write_text(migrated, encoding="utf-8")
                self._ps_text = migrated
                self._lbl_version.setText("v3")
                self._lbl_version.setStyleSheet(
                    "background:#1a2a1a;color:#98c379;border-radius:3px;"
                    "padding:2px 8px;font-size:10px;font-weight:bold;"
                )
                self._btn_migrate.setVisible(False)
                self._render()
                QMessageBox.information(self, "Gotowe", "PS.md zaktualizowany do formatu SSS v3.")
            except OSError as e:
                QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać pliku:\n{e}")

    # -- Render: Prompt -------------------------------------------------------

    def _render_prompt_tab(self, text: str) -> None:
        meta = _parse_meta(_read_section(text, "meta"))

        self._lbl_project.setText(meta.get("project", "—") or "—")
        self._lbl_created.setText(meta.get("created", "—") or "—")

        length = meta.get("prompt_length", "—")
        threshold = meta.get("threshold", "—")
        self._lbl_prompt_len.setText(f"{length} / {threshold} zn.")

        status = meta.get("status", "—")
        if _is_empty(status):
            self._lbl_ps_status.setText("—")
            self._lbl_ps_status.setStyleSheet(_LBL_DIM)
        elif status == "scored":
            self._lbl_ps_status.setText("● scored")
            self._lbl_ps_status.setStyleSheet(_LBL_OK)
        elif status == "complete":
            self._lbl_ps_status.setText("● kompletny")
            self._lbl_ps_status.setStyleSheet(_LBL_OK)
        elif status == "skipped_too_short":
            self._lbl_ps_status.setText("⚠ za krótki prompt")
            self._lbl_ps_status.setStyleSheet(_LBL_WARN)
        elif status == "intake_incomplete":
            self._lbl_ps_status.setText("◌ intake w toku")
            self._lbl_ps_status.setStyleSheet(_LBL_WARN)
        else:
            self._lbl_ps_status.setText(f"◌ {status}")
            self._lbl_ps_status.setStyleSheet(_LBL_WARN)

        prompt_text = _read_section(text, "prompt")
        if _is_empty(prompt_text) or prompt_text == "{{prompt}}":
            self._prompt_view.setPlainText("(brak promptu)")
        else:
            self._prompt_view.setPlainText(prompt_text)

    # -- Render: Pytania -------------------------------------------------------

    def _render_pytania_tab(self, text: str) -> None:
        _clear_content(self._pytania_lay)
        lay = self._pytania_lay

        rounds = [
            ("Runda 1 — Pytania statyczne (główny Claude)", "round_1", "#61afef", False),
            ("Runda 2 — Pytania od sędziów", "round_2", "#e5c07b", True),
            ("Runda 3 — Pytania od sędziów", "round_3", "#c678dd", True),
        ]

        for i, (title, section_name, color, has_source) in enumerate(rounds):
            _insert(lay, _section_label(title, color))

            section = _read_section(text, section_name)
            questions = _parse_round(section)

            if not questions:
                empty = QLabel("(brak danych)")
                empty.setStyleSheet(_LBL_DIM)
                _insert(lay, empty)
            else:
                for idx, qa in enumerate(questions, 1):
                    _insert(lay, self._make_qa_card(idx, qa, color, has_source))

                # proposals_log jeśli dostępny
                proposals = questions[0].get("proposals_log", "") if questions else ""
                if not _is_empty(proposals):
                    _insert(lay, self._make_proposals_log_card(proposals, color))

            if i < len(rounds) - 1:
                _insert(lay, _sep())

    def _make_qa_card(self, idx: int, qa: dict[str, str], color: str, has_source: bool) -> QFrame:
        card = QFrame()
        card.setStyleSheet(_CARD)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        # Pytanie
        q_row = QHBoxLayout()
        q_num = QLabel(f"Q{idx}")
        q_num.setStyleSheet(
            f"color:{color};font-size:10px;font-weight:bold;"
            "background:transparent;border:none;min-width:24px;"
        )
        q_row.addWidget(q_num)

        q_val = qa.get("q", "—")
        q_lbl = QLabel(q_val if not _is_empty(q_val) else "—")
        q_lbl.setStyleSheet("color:#cccccc;font-size:10px;background:transparent;border:none;")
        q_lbl.setWordWrap(True)
        q_row.addWidget(q_lbl, stretch=1)

        if has_source and not _is_empty(qa.get("source", "")):
            src = qa["source"]
            src_color = _JUDGE_COLORS.get(src, "#9d9d9d")
            src_lbl = QLabel(_JUDGE_LABELS.get(src, src))
            src_lbl.setStyleSheet(
                f"color:{src_color};font-size:9px;font-weight:bold;"
                f"background:#1e1e1e;border:1px solid {src_color}44;"
                "border-radius:3px;padding:1px 6px;"
            )
            q_row.addWidget(src_lbl)
        lay.addLayout(q_row)

        # Odpowiedź
        a_val = qa.get("a", "")
        if not _is_empty(a_val):
            a_row = QHBoxLayout()
            a_pfx = QLabel("A:")
            a_pfx.setStyleSheet(
                "color:#98c379;font-size:10px;font-weight:bold;"
                "background:transparent;border:none;min-width:24px;"
            )
            a_row.addWidget(a_pfx)
            a_lbl = QLabel(a_val)
            a_lbl.setStyleSheet(
                "color:#a8c0a8;font-size:10px;background:transparent;border:none;"
            )
            a_lbl.setWordWrap(True)
            a_row.addWidget(a_lbl, stretch=1)
            lay.addLayout(a_row)

        return card

    def _make_proposals_log_card(self, proposals: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:#1a1a1a;border-left:2px solid {color}44;"
            "border-top:none;border-right:none;border-bottom:none;"
            "border-radius:0px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 4, 8, 4)
        lay.setSpacing(2)

        hdr = QLabel("proposals_log")
        hdr.setStyleSheet(f"color:{color}66;font-size:9px;background:transparent;")
        lay.addWidget(hdr)

        lbl = QLabel(proposals)
        lbl.setStyleSheet("color:#787878;font-size:9px;background:transparent;")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        return card

    # -- Render: Oceny --------------------------------------------------------

    def _render_oceny_tab(self, text: str) -> None:
        _clear_content(self._oceny_lay)
        lay = self._oceny_lay

        # Score 1 i 2
        for title, section_name in [
            ("Score 1 — Kompetencje Biznesowe i Techniczne", "score_competence"),
            ("Score 2 — Architektura", "score_architecture"),
        ]:
            _insert(lay, _section_label(title))
            section = _read_section(text, section_name)
            judges = _parse_judges(section)

            if not judges:
                empty = QLabel("(brak danych)")
                empty.setStyleSheet(_LBL_DIM)
                _insert(lay, empty)
            else:
                for judge in judges:
                    _insert(lay, self._make_judge_score_card(judge))
            _insert(lay, _sep())

        # Score 3 — Trudność
        _insert(lay, _section_label("Score 3 — Trudność projektu"))
        diff_section = _read_section(text, "score_difficulty")
        diff_meta = _parse_meta(diff_section)
        _insert(lay, self._make_difficulty_card(diff_meta))
        _insert(lay, _sep())

        # Podsumowanie
        _insert(lay, _section_label("Podsumowanie końcowe"))
        summary = _read_section(text, "summary")
        if summary:
            sum_view = QPlainTextEdit()
            sum_view.setReadOnly(True)
            sum_view.setFont(_FONT_MONO)
            sum_view.setFixedHeight(110)
            sum_view.setPlainText(summary)
            sum_view.setStyleSheet(
                "QPlainTextEdit{background:#0d1117;color:#98c379;"
                "border:1px solid #3c3c3c;border-radius:4px;padding:6px;}"
            )
            _insert(lay, sum_view)
        else:
            empty = QLabel("(brak podsumowania)")
            empty.setStyleSheet(_LBL_DIM)
            _insert(lay, empty)

    def _make_judge_score_card(self, judge: dict[str, str]) -> QFrame:
        name = judge.get("name", "")
        color = _JUDGE_COLORS.get(name, "#9d9d9d")
        label = _JUDGE_LABELS.get(name, name)
        is_aggregate = name == "aggregate"

        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{'#18182e' if is_aggregate else '#1e1e1e'};"
            f"border:1px solid {color}{'66' if is_aggregate else '33'};"
            "border-radius:4px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)

        # Nagłówek z nazwą i oceną
        hdr_row = QHBoxLayout()
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"color:{color};font-size:10px;font-weight:bold;"
            "background:transparent;border:none;"
        )
        hdr_row.addWidget(name_lbl)
        hdr_row.addStretch()

        if is_aggregate:
            for field in ("mean", "median", "distribution"):
                val = judge.get(field, "")
                if not _is_empty(val):
                    lbl = QLabel(f"{field}: {val}")
                    lbl.setStyleSheet(
                        f"color:{color};font-size:9px;background:transparent;border:none;"
                    )
                    hdr_row.addWidget(lbl)
                    hdr_row.addSpacing(10)
            top = judge.get("top_advice", "")
            if not _is_empty(top):
                top_lbl = QLabel(f"top: {top}")
                top_lbl.setStyleSheet(
                    f"color:{color}bb;font-size:9px;background:transparent;border:none;"
                )
                top_lbl.setWordWrap(True)
                lay.addLayout(hdr_row)
                lay.addWidget(top_lbl)
                return card
        else:
            score = judge.get("score", "")
            if not _is_empty(score):
                score_lbl = QLabel(f"★ {score}")
                score_lbl.setStyleSheet(
                    f"color:{color};font-size:11px;font-weight:bold;"
                    "background:transparent;border:none;"
                )
                hdr_row.addWidget(score_lbl)

        lay.addLayout(hdr_row)

        comment = judge.get("comment", "")
        if not _is_empty(comment):
            c_lbl = QLabel(comment)
            c_lbl.setStyleSheet(
                "color:#9090a0;font-size:10px;background:transparent;border:none;"
            )
            c_lbl.setWordWrap(True)
            lay.addWidget(c_lbl)

        return card

    def _make_difficulty_card(self, meta: dict[str, str]) -> QFrame:
        card = QFrame()
        card.setStyleSheet(_CARD)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        score = meta.get("score", "—")
        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("Ocena trudności:", styleSheet=_LBL_KEY))
        score_color = "#98c379" if not _is_empty(score) else "#5c6370"
        score_lbl = QLabel(score if not _is_empty(score) else "—")
        score_lbl.setStyleSheet(
            f"color:{score_color};font-size:12px;font-weight:bold;"
        )
        score_row.addWidget(score_lbl)
        score_row.addStretch()
        lay.addLayout(score_row)

        for field, label in [
            ("reasoning", "Uzasadnienie:"),
            ("main_risks", "Główne ryzyka:"),
        ]:
            val = meta.get(field, "")
            if not _is_empty(val):
                row = QHBoxLayout()
                row.addWidget(QLabel(label, styleSheet=_LBL_KEY))
                lbl = QLabel(val)
                lbl.setStyleSheet(_LBL_VAL)
                lbl.setWordWrap(True)
                row.addWidget(lbl, stretch=1)
                lay.addLayout(row)

        return card

    # -- Render: Porady sędziów -----------------------------------------------

    def _render_porady_tab(self, text: str) -> None:
        _clear_content(self._porady_lay)
        lay = self._porady_lay

        # Zbierz porady per sędzia z obu sekcji score
        advice_map: dict[str, list[tuple[str, str]]] = {}
        for section_name, section_title in [
            ("score_competence", "Kompetencje"),
            ("score_architecture", "Architektura"),
        ]:
            section = _read_section(text, section_name)
            for judge in _parse_judges(section):
                name = judge.get("name", "")
                if name == "aggregate":
                    continue
                advice = judge.get("advice", "")
                if not _is_empty(advice):
                    advice_map.setdefault(name, []).append((section_title, advice))

        if not advice_map:
            empty = QLabel(
                "Brak porad — PS.md nie zawiera jeszcze ocen sędziów.\n"
                "Uruchom Rundę Wstępną SSS, aby wypełnić ten panel."
            )
            empty.setStyleSheet(_LBL_DIM)
            empty.setWordWrap(True)
            _insert(lay, empty)
            return

        for judge_name in _JUDGE_ORDER:
            if judge_name not in advice_map:
                continue
            color = _JUDGE_COLORS.get(judge_name, "#9d9d9d")
            label = _JUDGE_LABELS.get(judge_name, judge_name)

            hdr = _section_label(f"▸  {label}", color)
            _insert(lay, hdr)

            for section_title, advice in advice_map[judge_name]:
                card = QFrame()
                card.setStyleSheet(
                    f"QFrame{{background:#1e1e1e;border-left:3px solid {color};"
                    "border-top:none;border-right:none;border-bottom:none;"
                    "border-radius:0px;}}"
                )
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(12, 5, 8, 5)
                card_lay.setSpacing(2)

                src_lbl = QLabel(section_title)
                src_lbl.setStyleSheet(
                    f"color:{color}88;font-size:9px;background:transparent;"
                )
                card_lay.addWidget(src_lbl)

                adv_lbl = QLabel(advice)
                adv_lbl.setStyleSheet(
                    "color:#cccccc;font-size:10px;background:transparent;"
                )
                adv_lbl.setWordWrap(True)
                card_lay.addWidget(adv_lbl)

                _insert(lay, card)

            _insert(lay, _sep())
