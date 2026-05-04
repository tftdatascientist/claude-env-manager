"""AI-powered project setup wizard for Claude Manager.

Uses Claude Code CLI (`cc --print`) — no API key required.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QLineEdit, QScrollArea, QWidget, QFrame,
    QStackedWidget, QProgressBar, QMessageBox, QFileDialog,
    QGroupBox, QSizePolicy,
)

def _find_cc() -> str | None:
    """Find Claude Code binary — prefers claude.exe (direct, no cmd.exe needed)."""
    import os
    home = Path(os.path.expanduser("~"))

    if sys.platform == "win32":
        npm = home / "AppData" / "Roaming" / "npm"
        # Prefer the compiled .exe — avoids cmd.exe special-char issues entirely
        exe = npm / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
        # Fallback: .cmd wrappers (handled later with PowerShell)
        for c in [npm / "claude.CMD", npm / "claude.cmd", npm / "cc.cmd", npm / "cc"]:
            if c.exists():
                return str(c)

    # Unix / fallback
    for name in ("cc", "claude"):
        found = shutil.which(name)
        if found:
            return found
    return None


_CC_PATH: str | None = _find_cc()
_AVAILABLE: bool = _CC_PATH is not None

# ── Styles ────────────────────────────────────────────────────────────────────

_S = {
    'input': (
        "QLineEdit { background: #21252b; color: #abb2bf; border: 1px solid #3e4451;"
        " border-radius: 3px; padding: 4px 8px; font-size: 11px; }"
        "QLineEdit:focus { border-color: #61afef; }"
    ),
    'textarea': (
        "QPlainTextEdit { background: #1e2127; color: #abb2bf; border: 1px solid #3e4451;"
        " border-radius: 3px; font-size: 11px; }"
        "QPlainTextEdit:focus { border-color: #61afef; }"
    ),
    'btn': (
        "QPushButton { background: #3e4451; color: #abb2bf; border: 1px solid #4b5263;"
        " border-radius: 3px; padding: 4px 10px; font-size: 11px; }"
        "QPushButton:hover { background: #4b5263; color: #e5c07b; }"
        "QPushButton:disabled { color: #5c6370; background: #2c313a; }"
    ),
    'btn_primary': (
        "QPushButton { background: #2d4a2d; color: #98c379; border: 1px solid #3a5c3a;"
        " border-radius: 3px; padding: 6px 16px; font-size: 12px; font-weight: bold; }"
        "QPushButton:hover { background: #3a5c3a; }"
        "QPushButton:disabled { color: #5c6370; background: #1e2127; border-color: #2c313a; }"
    ),
    'btn_regen': (
        "QPushButton { background: transparent; color: #4b5263; border: none;"
        " font-size: 10px; padding: 1px 5px; border-radius: 2px; }"
        "QPushButton:hover { color: #61afef; background: #2c313a; }"
        "QPushButton:disabled { color: #3e4451; }"
    ),
    'group': (
        "QGroupBox { color: #e5c07b; font-size: 11px; font-weight: bold;"
        " border: 1px solid #3e4451; border-radius: 4px; margin-top: 10px; padding-top: 8px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
    ),
    'error': (
        "background: #2d1b1b; border: 1px solid #5c3333; border-radius: 4px;"
        " color: #e06c75; padding: 8px 12px; font-size: 11px;"
    ),
    'status': "color: #98c379; font-size: 12px; font-family: Consolas;",
    'sep': "color: #3e4451;",
    'field_label': "color: #6b7280; font-size: 10px; font-family: Consolas; min-width: 160px;",
}

# ── Section / field definitions ───────────────────────────────────────────────

SECTIONS = {
    'metadata': {
        'title': 'CLAUDE.md — metadane',
        'fields': [
            ('one_liner',       'One-liner',           1),
            ('stack',           'Stack',               4),
            ('run_command',     'Run command',         3),
            ('coding_rules',    'Coding rules',        4),
            ('key_files_table', 'Key files (tabela)',  4),
        ],
    },
    'architecture': {
        'title': 'ARCHITECTURE.md',
        'fields': [
            ('directory_tree',           'Directory tree',      7),
            ('modules_table',            'Modules table',       4),
            ('data_flow',                'Data flow',           3),
            ('architectural_decisions',  'Arch. decisions',     4),
            ('external_deps_table',      'External deps',       4),
        ],
    },
    'conventions': {
        'title': 'CONVENTIONS.md',
        'fields': [
            ('naming_conventions',   'Naming conventions', 4),
            ('code_structure_rules', 'Code structure',     3),
            ('formatting_rules',     'Formatting',         3),
            ('testing_rules',        'Testing',            3),
            ('git_conventions',      'Git conventions',    2),
        ],
    },
    'plan': {
        'title': 'PLAN.md',
        'fields': [
            ('initial_goal',      'Initial goal',           1),
            ('initial_steps',     'Initial steps',          5),
            ('initial_decisions', 'Initial decisions',      3),
        ],
    },
}

# ── Prompts ───────────────────────────────────────────────────────────────────

_JSON_HEADER = (
    "ZADANIE: Wygeneruj RAW JSON. "
    "NIE pytaj o nic. NIE komentuj. NIE zadawaj pytań. "
    "Twoja odpowiedź to WYŁĄCZNIE jeden obiekt JSON zaczynający się od { i kończący na }. "
    "Zero tekstu przed ani po.\n\n"
)

_RULES = (
    "\n\nWYMAGANIA FORMATU (bezwzględne):\n"
    "- Surowy obiekt JSON — nic poza nim\n"
    "- BEZ ```json fences\n"
    "- Escape \\n wewnątrz stringów\n"
    "- Wszystkie wartości: stringi, max 600 znaków\n"
    "- Jeśli nie wiesz — wymyśl sensowne placeholder"
)


def _p_meta(desc: str) -> str:
    return f"""{_JSON_HEADER}Generujesz metadane projektu Claude Code (Python) na podstawie opisu.

OPIS PROJEKTU:
{desc}

Zwróć JSON z polami (wartości po polsku):
- "project_title": krótki tytuł (max 60 znaków)
- "one_liner": jedno zdanie czym jest projekt (max 140 znaków)
- "stack": język + framework + biblioteki, prosty markdown
- "run_command": jak uruchomić projekt, blok kodu bash
- "coding_rules": 3-5 zasad kodowania jako markdown lista
- "key_files_table": markdown tabela "Plik | Rola" z 3-5 wierszami
{_RULES}"""


def _p_arch(desc: str, meta: dict) -> str:
    return f"""{_JSON_HEADER}Generujesz treść ARCHITECTURE.md dla projektu Python.

OPIS: {desc}
STACK: {meta.get('stack', '')}
ONE-LINER: {meta.get('one_liner', '')}

Zwróć JSON z polami (wartości po polsku, zwięzłe):
- "directory_tree": ASCII tree struktury katalogów, max 15 linii
- "modules_table": tabela markdown "Moduł | Plik(i) | Odpowiedzialność", 3-5 wierszy
- "data_flow": 2-3 zdania opisujące przepływ danych
- "architectural_decisions": 3-4 punkty z uzasadnieniem decyzji
- "external_deps_table": tabela markdown "Lib/API | Cel | Wersja", 3-5 wierszy
{_RULES}"""


def _p_conv(desc: str, meta: dict) -> str:
    return f"""{_JSON_HEADER}Generujesz treść CONVENTIONS.md dla projektu Python.

OPIS: {desc}
STACK: {meta.get('stack', '')}

Zwróć JSON z polami (wartości po polsku, dopasowane do stacku):
- "naming_conventions": 4 punkty — konwencje nazw (pliki, klasy, funkcje, zmienne)
- "code_structure_rules": 2-3 punkty o strukturze kodu
- "formatting_rules": 2-3 punkty o formatowaniu (PEP8, długość linii)
- "testing_rules": 2-3 punkty o testach (pytest)
- "git_conventions": 2 punkty o commitach (feat/fix/docs...)
{_RULES}"""


def _p_plan(desc: str, meta: dict) -> str:
    return f"""{_JSON_HEADER}Generujesz treść PLAN.md — cel i pierwsze kroki projektu Python.

OPIS: {desc}
ONE-LINER: {meta.get('one_liner', '')}

Zwróć JSON z polami (wartości po polsku):
- "initial_goal": jedno konkretne zdanie — cel pierwszej sesji dev
- "initial_steps": markdown checklist 3-5 kroków w formacie "- [ ] krok"
- "initial_decisions": 2-3 punkty już podjętych decyzji technicznych
{_RULES}"""


def _p_regen_field(desc: str, key: str, ctx: dict) -> str:
    ctx_str = json.dumps(ctx, ensure_ascii=False)[:800]
    return f"""{_JSON_HEADER}Regenerujesz JEDNO pole JSON: "{key}".

OPIS PROJEKTU: {desc}
KONTEKST (inne pola): {ctx_str}

Zwróć TYLKO: {{"{key}": "<nowa wartość>"}}
{_RULES}"""


# ── JSON parsing ──────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    text = text.strip()
    for candidate in [
        text,
        re.search(r'```json\s*([\s\S]*?)```', text, re.I) and re.search(r'```json\s*([\s\S]*?)```', text, re.I).group(1).strip(),
        re.search(r'\{[\s\S]*\}', text) and re.search(r'\{[\s\S]*\}', text).group(0),
    ]:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            pass
    raise ValueError(f"Nie znaleziono JSON: {text[:200]}")


# ── CC subprocess call ────────────────────────────────────────────────────────

def _call_cc(prompt: str) -> dict:
    """Run `claude --print <prompt>` directly via claude.exe (no cmd.exe/shell needed)."""
    import tempfile

    if not _CC_PATH:
        raise RuntimeError("Claude Code CLI (claude.exe) niedostępny.")

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # Neutral cwd — no project CLAUDE.md loaded as context
    neutral_cwd = tempfile.gettempdir()

    # Direct exe call — Python passes args as-is via CreateProcess, no shell interpretation
    # Special chars (<>|&) in prompt are safe: subprocess list→argv, never touches a shell
    result = subprocess.run(
        [_CC_PATH, "--print", prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        creationflags=flags,
        cwd=neutral_cwd,
    )
    output = result.stdout.strip()
    if result.returncode != 0 and not output:
        raise RuntimeError(result.stderr[:300] or f"claude exit {result.returncode}")
    return _parse_json(output)


# ── Worker threads ────────────────────────────────────────────────────────────

class _GenWorker(QThread):
    """Generates all 4 sections — metadata first, then arch/conv/plan in parallel."""
    status = Signal(str)
    ready = Signal(dict, str)   # fields, project_title
    failed = Signal(str)

    def __init__(self, desc: str, regen_section: str | None = None, cur: dict | None = None):
        super().__init__()
        self._desc = desc
        self._regen = regen_section
        self._cur = cur or {}

    def run(self) -> None:
        try:
            if self._regen:
                self._run_regen()
            else:
                self._run_full()
        except Exception as e:
            self.failed.emit(str(e))

    def _run_full(self) -> None:
        self.status.emit("Generowanie metadanych…")
        meta = _call_cc(_p_meta(self._desc))
        title = meta.get("project_title", "")
        base = {
            "one_liner":       meta.get("one_liner", ""),
            "stack":           meta.get("stack", ""),
            "run_command":     meta.get("run_command", ""),
            "coding_rules":    meta.get("coding_rules", ""),
            "key_files_table": meta.get("key_files_table", ""),
        }

        self.status.emit("Generowanie architektury, konwencji i planu…")
        with ThreadPoolExecutor(max_workers=3) as ex:
            fa = ex.submit(_call_cc, _p_arch(self._desc, base))
            fc = ex.submit(_call_cc, _p_conv(self._desc, base))
            fp = ex.submit(_call_cc, _p_plan(self._desc, base))
            arch, conv, plan = fa.result(), fc.result(), fp.result()

        fields = {**base,
            "directory_tree":          arch.get("directory_tree", ""),
            "modules_table":           arch.get("modules_table", ""),
            "data_flow":               arch.get("data_flow", ""),
            "architectural_decisions": arch.get("architectural_decisions", ""),
            "external_deps_table":     arch.get("external_deps_table", ""),
            "naming_conventions":      conv.get("naming_conventions", ""),
            "code_structure_rules":    conv.get("code_structure_rules", ""),
            "formatting_rules":        conv.get("formatting_rules", ""),
            "testing_rules":           conv.get("testing_rules", ""),
            "git_conventions":         conv.get("git_conventions", ""),
            "initial_goal":            plan.get("initial_goal", ""),
            "initial_steps":           plan.get("initial_steps", ""),
            "initial_decisions":       plan.get("initial_decisions", ""),
        }
        self.ready.emit(fields, title)

    def _run_regen(self) -> None:
        sec = self._regen
        self.status.emit(f"Regeneracja sekcji {sec}…")
        meta = {"one_liner": self._cur.get("one_liner", ""), "stack": self._cur.get("stack", "")}
        key_map = {
            "metadata":     (_p_meta(self._desc),         ["one_liner","stack","run_command","coding_rules","key_files_table"], True),
            "architecture": (_p_arch(self._desc, meta),   ["directory_tree","modules_table","data_flow","architectural_decisions","external_deps_table"], False),
            "conventions":  (_p_conv(self._desc, meta),   ["naming_conventions","code_structure_rules","formatting_rules","testing_rules","git_conventions"], False),
            "plan":         (_p_plan(self._desc, meta),   ["initial_goal","initial_steps","initial_decisions"], False),
        }
        prompt, keys, has_title = key_map[sec]
        parsed = _call_cc(prompt)
        result = {k: parsed.get(k, self._cur.get(k, "")) for k in keys}
        title = parsed.get("project_title", "") if has_title else ""
        self.ready.emit(result, title)


class _FieldWorker(QThread):
    done = Signal(str, str)
    failed = Signal(str)

    def __init__(self, desc: str, key: str, ctx: dict):
        super().__init__()
        self._desc, self._key_field, self._ctx = desc, key, ctx

    def run(self) -> None:
        try:
            parsed = _call_cc(_p_regen_field(self._desc, self._key_field, self._ctx))
            self.done.emit(self._key_field, str(parsed.get(self._key_field, "")))
        except Exception as e:
            self.failed.emit(str(e))


# ── File writer ───────────────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    _PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    s = re.sub(r"[^a-z0-9]+", "_", title.lower().translate(_PL)).strip("_")
    return s or "projekt"


def _as_bullets(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(f"- {l}" if not l.startswith("-") else l for l in lines)


def write_project_files(dest: Path, title: str, fields: dict) -> None:
    """Create CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md, PLAN.md in dest."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── CLAUDE.md ──────────────────────────────────────────────────────────
    stack_first = (fields.get("stack", "Python 3.13+").splitlines() or ["Python 3.13+"])[0].lstrip("- ")
    stack_bullets = _as_bullets(fields.get("stack", "Python 3.13+"))
    key_files_bullets = _as_bullets(fields.get("key_files_table", ""))
    claude_md = f"""# {title}

<!-- SECTION:project -->
- name: {title}
- type:
- client:
- stack: {stack_first}
<!-- /SECTION:project -->

{fields.get("one_liner", "")}

## Instrukcje dla agenta

Agent edytuje wyłącznie `PLAN.md` w trakcie rundy.
Pozostałe pliki (`ARCHITECTURE.md`, `CONVENTIONS.md`) są chronione.

## Stack
<!-- SECTION:stack -->
{stack_bullets}
<!-- /SECTION:stack -->

## Key Files
<!-- SECTION:key_files -->
{key_files_bullets or "- "}
<!-- /SECTION:key_files -->

## Zasady kodowania

{fields.get("coding_rules", "")}

## Uruchomienie

{fields.get("run_command", "")}

## Off-limits w trakcie rundy

- Nie edytuj `CLAUDE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` bezpośrednio
- Nie commituj bez walidacji
"""

    # ── ARCHITECTURE.md ────────────────────────────────────────────────────
    decisions_raw = fields.get("architectural_decisions", "")
    decisions_pcc = "\n".join(
        f"- [ ] {l.lstrip('- ')} | {datetime.now().strftime('%Y-%m-%d')} | AI Wizard"
        for l in decisions_raw.splitlines() if l.strip()
    )
    arch_md = f"""## Overview
<!-- SECTION:overview -->
{fields.get("data_flow", "")}
<!-- /SECTION:overview -->

## Directory Structure

```
{fields.get("directory_tree", "")}
```

## Components
<!-- SECTION:components -->
{_as_bullets(fields.get("modules_table", "")) or "- "}
<!-- /SECTION:components -->

## External Dependencies
<!-- SECTION:external_deps -->
{_as_bullets(fields.get("external_deps_table", "")) or "- python: 3.13+"}
<!-- /SECTION:external_deps -->

## Constraints
<!-- SECTION:constraints -->
<!-- /SECTION:constraints -->

## Data Flow
<!-- SECTION:data_flow -->
{fields.get("data_flow", "")}
<!-- /SECTION:data_flow -->

## Decisions
<!-- SECTION:decisions -->
{decisions_pcc or "<!-- brak decyzji -->"}
<!-- /SECTION:decisions -->
"""

    # ── CONVENTIONS.md ─────────────────────────────────────────────────────
    def _sec(key: str) -> str:
        return _as_bullets(fields.get(key, "")) or "- "

    conv_md = f"""## Naming
<!-- SECTION:naming -->
{_sec("naming_conventions")}
<!-- /SECTION:naming -->

## File Layout
<!-- SECTION:file_layout -->
{_as_bullets(fields.get("directory_tree", "")) or "- src/ — kod"}
<!-- /SECTION:file_layout -->

## Code Style
<!-- SECTION:code_style -->
{_sec("code_structure_rules")}
{_sec("formatting_rules")}
<!-- /SECTION:code_style -->

## Commit Style
<!-- SECTION:commit_style -->
{_sec("git_conventions")}
<!-- /SECTION:commit_style -->

## Testing
<!-- SECTION:testing -->
{_sec("testing_rules")}
<!-- /SECTION:testing -->

## Anti-patterns
<!-- SECTION:anti_patterns -->
<!-- /SECTION:anti_patterns -->
"""

    # ── PLAN.md (PCC v2.0 strict) ──────────────────────────────────────────
    steps = [l.strip() for l in fields.get("initial_steps", "").splitlines() if l.strip()]
    first_task = steps[0].lstrip("- [ ]").strip() if steps else ""
    next_lines = "\n".join(
        l if l.startswith("- [ ]") else f"- [ ] {l.lstrip('- ')}"
        for l in steps[1:]
    ) if len(steps) > 1 else "- [ ] "

    plan_md = f"""<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: {fields.get("initial_goal", "")}
- session: 1
- updated: {now}
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: {first_task}
- file:
- started: {now}
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
{next_lines}
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- {now} | Projekt zainicjalizowany przez AI Wizard
<!-- /SECTION:session_log -->
"""

    dest.mkdir(parents=True, exist_ok=True)
    for fname, content in [
        ("CLAUDE.md",       claude_md),
        ("ARCHITECTURE.md", arch_md),
        ("CONVENTIONS.md",  conv_md),
        ("PLAN.md",         plan_md),
    ]:
        (dest / fname).write_text(content, encoding="utf-8")


# ── Separator helper ──────────────────────────────────────────────────────────

def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(_S["sep"])
    return f


# ── Main dialog ───────────────────────────────────────────────────────────────

class AIProjectWizardDialog(QDialog):
    """AI-powered project setup wizard — describe → generate → review → create."""

    project_created = Signal(Path)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("✨ AI Project Wizard — Claude Manager")
        self.setMinimumSize(860, 660)
        self.setModal(True)

        self._desc: str = ""
        self._fields: dict[str, str] = {}
        self._project_title: str = ""
        self._worker: QThread | None = None
        self._editors: dict[str, QPlainTextEdit] = {}
        self._title_edit: QLineEdit | None = None
        self._slug_edit: QLineEdit | None = None
        self._slug_auto: bool = True

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        hdr = QLabel("✨ AI Project Wizard")
        hdr.setStyleSheet("color: #e5c07b; font-size: 14px; font-weight: bold;")
        root.addWidget(hdr)
        root.addWidget(_sep())

        self._pages = QStackedWidget()
        self._pages.addWidget(self._page_describe())    # 0
        self._pages.addWidget(self._page_generating())  # 1
        self._pages.addWidget(self._page_review())      # 2
        self._pages.addWidget(self._page_create())      # 3
        root.addWidget(self._pages, 1)

        self._err = QLabel()
        self._err.setStyleSheet(_S["error"])
        self._err.setWordWrap(True)
        self._err.setVisible(False)
        root.addWidget(self._err)

    # ── Page 0: describe ─────────────────────────────────────────────────

    def _page_describe(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        title = QLabel("Opisz projekt")
        title.setStyleSheet("color: #61afef; font-size: 13px; font-weight: bold;")
        lay.addWidget(title)

        info = QLabel(
            "Kilka zdań o tym co budujesz, w jakim stacku, dla kogo. "
            "Wizard wygeneruje CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md i PLAN.md."
        )
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setPlaceholderText(
            "Np.:\n\n"
            "CLI tool w Pythonie do zarządzania środowiskami Claude Code na Windows 11.\n"
            "GUI w PySide6, watchdog do monitorowania plików, pytest do testów.\n"
            "Projekt własny, desktop app, Python 3.13."
        )
        self._desc_edit.setStyleSheet(_S["textarea"])
        self._desc_edit.setFont(QFont("Consolas", 10))
        self._desc_edit.setMinimumHeight(180)
        self._desc_edit.textChanged.connect(self._on_desc_changed)
        lay.addWidget(self._desc_edit, 1)

        bottom = QHBoxLayout()
        self._char_lbl = QLabel("0 znaków  (min. 30)")
        self._char_lbl.setStyleSheet("color: #5c6370; font-size: 10px;")
        bottom.addWidget(self._char_lbl)
        bottom.addStretch()

        if _AVAILABLE:
            cc_info = QLabel(f"✓ cc: {_CC_PATH}")
            cc_info.setStyleSheet("color: #5c6370; font-size: 10px; font-family: Consolas;")
            bottom.addWidget(cc_info)
        else:
            warn = QLabel("⚠  cc (Claude Code) niedostępny w PATH")
            warn.setStyleSheet("color: #e06c75; font-size: 10px;")
            bottom.addWidget(warn)

        self._btn_gen = QPushButton("✨  Generuj szablon")
        self._btn_gen.setStyleSheet(_S["btn_primary"])
        self._btn_gen.setEnabled(False)
        self._btn_gen.clicked.connect(self._start_gen)
        bottom.addWidget(self._btn_gen)
        lay.addLayout(bottom)
        return w

    # ── Page 1: generating ───────────────────────────────────────────────

    def _page_generating(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(18)

        self._gen_lbl = QLabel("Inicjalizacja…")
        self._gen_lbl.setStyleSheet(_S["status"])
        self._gen_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._gen_lbl)

        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setFixedWidth(320)
        bar.setFixedHeight(6)
        bar.setStyleSheet(
            "QProgressBar { border: 1px solid #3e4451; border-radius: 3px;"
            " background: #21252b; }"
            "QProgressBar::chunk { background: #61afef; border-radius: 3px; }"
        )
        lay.addWidget(bar)

        self._btn_cancel_gen = QPushButton("Anuluj")
        self._btn_cancel_gen.setStyleSheet(_S["btn"])
        self._btn_cancel_gen.clicked.connect(self._cancel_worker)
        lay.addWidget(self._btn_cancel_gen, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── Page 2: review ───────────────────────────────────────────────────

    def _page_review(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Title / slug row
        meta = QHBoxLayout()
        meta.setSpacing(10)

        tc = QVBoxLayout()
        tc.setSpacing(3)
        tc.addWidget(QLabel("Tytuł projektu:"))
        self._title_edit = QLineEdit()
        self._title_edit.setStyleSheet(_S["input"])
        self._title_edit.textChanged.connect(self._on_title_changed)
        tc.addWidget(self._title_edit)
        meta.addLayout(tc, 2)

        sc = QVBoxLayout()
        sc.setSpacing(3)
        sc.addWidget(QLabel("Slug (nazwa folderu):"))
        self._slug_edit = QLineEdit()
        self._slug_edit.setStyleSheet(_S["input"])
        self._slug_edit.setFont(QFont("Consolas", 10))
        self._slug_edit.textEdited.connect(self._on_slug_edited)
        sc.addWidget(self._slug_edit)
        meta.addLayout(sc, 1)

        lay.addLayout(meta)
        lay.addWidget(_sep())

        # Scrollable field sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(6)
        inner_lay.setContentsMargins(2, 2, 8, 2)

        for sec_key, sec_def in SECTIONS.items():
            gb = QGroupBox(sec_def["title"])
            gb.setStyleSheet(_S["group"])
            gb_lay = QVBoxLayout(gb)
            gb_lay.setSpacing(5)

            regen_btn = QPushButton("↻  regeneruj sekcję")
            regen_btn.setStyleSheet(_S["btn_regen"])
            regen_btn.clicked.connect(lambda _, k=sec_key: self._regen_section(k))
            gb_lay.addWidget(regen_btn, alignment=Qt.AlignmentFlag.AlignRight)

            for fkey, flabel, frows in sec_def["fields"]:
                row = QHBoxLayout()
                row.setSpacing(6)

                lbl = QLabel(flabel)
                lbl.setStyleSheet(_S["field_label"])
                lbl.setFixedWidth(165)
                lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
                row.addWidget(lbl)

                te = QPlainTextEdit()
                te.setStyleSheet(_S["textarea"])
                te.setFont(QFont("Consolas", 9))
                te.setFixedHeight(frows * 17 + 10)
                te.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row.addWidget(te, 1)
                self._editors[fkey] = te

                rb = QPushButton("↻")
                rb.setStyleSheet(_S["btn_regen"])
                rb.setFixedWidth(22)
                rb.setToolTip(f"Regeneruj: {flabel}")
                rb.clicked.connect(lambda _, k=fkey: self._regen_field(k))
                row.addWidget(rb)

                gb_lay.addLayout(row)

            inner_lay.addWidget(gb)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        nav = QHBoxLayout()
        nav.addStretch()
        back = QPushButton("← Wróć")
        back.setStyleSheet(_S["btn"])
        back.clicked.connect(lambda: self._pages.setCurrentIndex(0))
        nav.addWidget(back)
        nxt = QPushButton("→ Utwórz projekt")
        nxt.setStyleSheet(_S["btn_primary"])
        nxt.clicked.connect(self._go_create)
        nav.addWidget(nxt)
        lay.addLayout(nav)
        return w

    # ── Page 3: create ───────────────────────────────────────────────────

    def _page_create(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        title = QLabel("Utwórz projekt na dysku")
        title.setStyleSheet("color: #61afef; font-size: 13px; font-weight: bold;")
        lay.addWidget(title)

        info = QLabel(
            "Wskaż katalog nadrzędny. Zostanie w nim utworzony podfolder o nazwie sluga "
            "z plikami CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md i PLAN.md."
        )
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Katalog nadrzędny…")
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setStyleSheet(_S["input"])
        self._dir_edit.textChanged.connect(self._update_dest)
        dir_row.addWidget(self._dir_edit, 1)
        btn_dir = QPushButton("Wybierz…")
        btn_dir.setStyleSheet(_S["btn"])
        btn_dir.clicked.connect(self._pick_dir)
        dir_row.addWidget(btn_dir)
        lay.addLayout(dir_row)

        self._dest_lbl = QLabel()
        self._dest_lbl.setStyleSheet("color: #5c6370; font-size: 10px; font-family: Consolas;")
        lay.addWidget(self._dest_lbl)

        lay.addStretch()

        nav = QHBoxLayout()
        nav.addStretch()
        back = QPushButton("← Wróć")
        back.setStyleSheet(_S["btn"])
        back.clicked.connect(lambda: self._pages.setCurrentIndex(2))
        nav.addWidget(back)
        self._btn_do_create = QPushButton("✓  Utwórz pliki projektu")
        self._btn_do_create.setStyleSheet(_S["btn_primary"])
        self._btn_do_create.setEnabled(False)
        self._btn_do_create.clicked.connect(self._do_create)
        nav.addWidget(self._btn_do_create)
        lay.addLayout(nav)
        return w

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_desc_changed(self) -> None:
        self._desc = self._desc_edit.toPlainText()
        n = len(self._desc)
        self._char_lbl.setText(f"{n} znaków  (min. 30)")
        self._btn_gen.setEnabled(n >= 30 and _AVAILABLE)

    def _on_title_changed(self, text: str) -> None:
        self._project_title = text
        if self._slug_auto and self._slug_edit:
            self._slug_edit.setText(_slugify(text))

    def _on_slug_edited(self, _: str) -> None:
        self._slug_auto = False

    def _start_gen(self) -> None:
        if not _AVAILABLE:
            self._show_err("Claude Code CLI (cc) niedostępny w PATH — uruchom CM z poziomu CC.")
            return
        self._hide_err()
        self._slug_auto = True
        self._pages.setCurrentIndex(1)
        self._worker = _GenWorker(self._desc)
        self._worker.status.connect(self._gen_lbl.setText)
        self._worker.ready.connect(self._on_gen_ready)
        self._worker.failed.connect(self._on_gen_fail)
        self._worker.start()

    def _on_gen_ready(self, fields: dict, title: str) -> None:
        self._fields.update(fields)
        if title:
            self._project_title = title
        for k, te in self._editors.items():
            te.setPlainText(fields.get(k, ""))
        if self._title_edit:
            self._title_edit.setText(self._project_title)
        if self._slug_edit:
            self._slug_edit.setText(_slugify(self._project_title))
            self._slug_auto = True
        self._pages.setCurrentIndex(2)

    def _on_gen_fail(self, msg: str) -> None:
        self._show_err(f"Błąd generowania: {msg}")
        self._pages.setCurrentIndex(0)

    def _cancel_worker(self) -> None:
        if self._worker:
            self._worker.terminate()
        self._pages.setCurrentIndex(0)

    def _regen_section(self, sec_key: str) -> None:
        self._hide_err()
        cur = {k: te.toPlainText() for k, te in self._editors.items()}
        self._worker = _GenWorker(self._desc, regen_section=sec_key, cur=cur)
        self._worker.status.connect(self._gen_lbl.setText)
        self._worker.ready.connect(lambda f, t: self._on_regen_sec_ready(f, t))
        self._worker.failed.connect(self._on_gen_fail)
        self._worker.start()

    def _on_regen_sec_ready(self, fields: dict, title: str) -> None:
        for k, v in fields.items():
            if k in self._editors:
                self._editors[k].setPlainText(v)
        if title and self._title_edit:
            self._title_edit.setText(title)
        self._fields.update(fields)

    def _regen_field(self, field_key: str) -> None:
        self._hide_err()
        ctx = {k: te.toPlainText() for k, te in self._editors.items()}
        self._worker = _FieldWorker(self._desc, field_key, ctx)
        self._worker.done.connect(self._on_field_ready)
        self._worker.failed.connect(self._on_gen_fail)
        self._worker.start()

    def _on_field_ready(self, key: str, value: str) -> None:
        if key in self._editors:
            self._editors[key].setPlainText(value)
        self._fields[key] = value

    def _go_create(self) -> None:
        for k, te in self._editors.items():
            self._fields[k] = te.toPlainText()
        if self._title_edit:
            self._project_title = self._title_edit.text().strip()
        self._update_dest()
        self._pages.setCurrentIndex(3)

    def _pick_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Wybierz katalog nadrzędny")
        if path:
            self._dir_edit.setText(path)

    def _update_dest(self) -> None:
        parent = self._dir_edit.text().strip()
        slug = (self._slug_edit.text().strip() if self._slug_edit else "") or _slugify(self._project_title)
        if parent and slug:
            dest = Path(parent) / slug
            self._dest_lbl.setText(f"Zostanie utworzony: {dest}")
            self._btn_do_create.setEnabled(True)
        else:
            self._dest_lbl.setText("Wskaż katalog i upewnij się, że tytuł projektu jest wypełniony.")
            self._btn_do_create.setEnabled(False)

    def _do_create(self) -> None:
        parent = self._dir_edit.text().strip()
        slug = (self._slug_edit.text().strip() if self._slug_edit else "") or _slugify(self._project_title)
        dest = Path(parent) / slug
        if dest.exists():
            QMessageBox.warning(self, "Błąd", f"Folder już istnieje:\n{dest}")
            return
        try:
            write_project_files(dest, self._project_title or slug, self._fields)
        except Exception as e:
            self._show_err(f"Błąd zapisu: {e}")
            return
        self.project_created.emit(dest)
        ans = QMessageBox.question(
            self, "Gotowe",
            f"Projekt '{self._project_title}' utworzony w:\n{dest}\n\n"
            "Otworzyć w VS Code?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            subprocess.Popen(["code", str(dest)], shell=True)
        self.accept()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _show_err(self, msg: str) -> None:
        self._err.setText(msg)
        self._err.setVisible(True)

    def _hide_err(self) -> None:
        self._err.setVisible(False)
