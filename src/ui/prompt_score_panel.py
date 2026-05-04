"""Panel 'Prompt Score' — podgląd PS.md projektu SSS (prompt, pytania, oceny, porady sędziów)."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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
    questions: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in section_text.splitlines():
        line = line.strip()
        if re.match(r"^- Q\d+:", line):
            if current and "q" in current:
                questions.append(current)
            _, _, q = line.partition(":")
            current = {"q": q.strip()}
        elif line.startswith("- A:"):
            current["a"] = line[4:].strip()
        elif line.startswith("- source_judge:"):
            current["source"] = line[15:].strip()
    if current and "q" in current:
        questions.append(current)
    return questions


def _is_empty(value: str) -> bool:
    return not value or value.strip() in ("-", "—", "")


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
# Główny panel                                                                  #
# --------------------------------------------------------------------------- #

class PromptScorePanel(QWidget):
    """Panel Prompt Score — wyświetla dane z PS.md projektu SSS."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ps_path: Path | None = None
        self._ps_text: str = ""
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
        self._tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #3c3c3c;background:#141414;}"
            "QTabBar::tab{background:#252526;color:#9d9d9d;padding:6px 16px;"
            "border:1px solid #3c3c3c;border-bottom:none;margin-right:2px;}"
            "QTabBar::tab:selected{background:#141414;color:#cccccc;}"
            "QTabBar::tab:hover{background:#2a2a2a;color:#cccccc;}"
        )

        self._tabs.addTab(self._build_prompt_tab(), "Prompt")
        self._tabs.addTab(self._build_pytania_tab(), "Pytania")
        self._tabs.addTab(self._build_oceny_tab(), "Oceny")
        self._tabs.addTab(self._build_porady_tab(), "Porady sędziów")

        root.addWidget(self._tabs, stretch=1)

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
        elif status == "complete":
            self._lbl_ps_status.setText("● kompletny")
            self._lbl_ps_status.setStyleSheet(_LBL_OK)
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
