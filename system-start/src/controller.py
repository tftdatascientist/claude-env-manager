"""
Python Controller — jedyny uprawniony zapis/walidacja plików MD poza PLAN.md.
Wszystkie operacje są idempotentne i walidowane przed zapisem.
"""
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent

PROTECTED_FILES = {"CLAUDE.md", "ARCHITECTURE.md", "CONVENTIONS.md"}
PLAN_FILE = BASE_DIR / "PLAN.md"
ARCHITECTURE_FILE = BASE_DIR / "ARCHITECTURE.md"

DECISION_LINE_RE = re.compile(r"^- \[.\] .+ \| \d{4}-\d{2}-\d{2} \| .+$")

SECTION_RE = re.compile(
    r"<!--\s*SECTION:(?P<name>\w+)\s*-->(?P<body>.*?)<!--\s*/SECTION:(?P=name)\s*-->",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    if path.name in PROTECTED_FILES:
        raise PermissionError(
            f"Zapis do {path.name} jest zablokowany w trakcie rundy. "
            "Użyj SKILL po zakończeniu rundy."
        )
    path.write_text(content, encoding="utf-8")


def _parse_sections(text: str) -> dict[str, str]:
    return {m.group("name"): m.group("body").strip() for m in SECTION_RE.finditer(text)}


def _replace_section(text: str, name: str, new_body: str) -> str:
    tag_open = f"<!-- SECTION:{name} -->"
    tag_close = f"<!-- /SECTION:{name} -->"
    replacement = f"{tag_open}\n{new_body}\n{tag_close}"
    pattern = re.compile(
        rf"<!--\s*SECTION:{name}\s*-->.*?<!--\s*/SECTION:{name}\s*-->",
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(f"Sekcja '{name}' nie istnieje w pliku.")
    return pattern.sub(replacement, text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_plan() -> dict[str, str]:
    """Zwraca słownik sekcji PLAN.md."""
    return _parse_sections(_read(PLAN_FILE))


def update_plan_section(section: str, new_body: str) -> None:
    """Nadpisuje jedną sekcję w PLAN.md po walidacji."""
    text = _read(PLAN_FILE)
    updated = _replace_section(text, section, new_body)
    _write(PLAN_FILE, updated)


def update_plan_meta(*, status: str | None = None, goal: str | None = None) -> None:
    """Aktualizuje pola status/goal w sekcji meta PLAN.md."""
    sections = read_plan()
    meta_lines = sections.get("meta", "").splitlines()
    result: list[str] = []
    for line in meta_lines:
        if status is not None and line.strip().startswith("- status:"):
            line = f"- status: {status}"
        if goal is not None and line.strip().startswith("- goal:"):
            line = f"- goal: {goal}"
        if line.strip().startswith("- updated:"):
            line = f"- updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result.append(line)
    update_plan_section("meta", "\n".join(result))


def mark_task_done(task_text: str) -> None:
    """Przenosi zadanie z sekcji 'next' do 'done' w PLAN.md."""
    sections = read_plan()
    next_lines = sections.get("next", "").splitlines()
    done_lines = sections.get("done", "").splitlines()

    moved = False
    remaining: list[str] = []
    for line in next_lines:
        if not moved and task_text in line and line.strip().startswith("- [ ]"):
            done_lines.append(line.replace("- [ ]", "- [x]"))
            moved = True
        else:
            remaining.append(line)

    if not moved:
        raise ValueError(f"Zadanie '{task_text}' nie znalezione w sekcji next.")

    text = _read(PLAN_FILE)
    text = _replace_section(text, "next", "\n".join(remaining))
    text = _replace_section(text, "done", "\n".join(done_lines))
    _write(PLAN_FILE, text)


def flush_plan() -> None:
    """
    Czyści PLAN.md po zakończeniu rundy:
    - sekcje next i done → puste
    - current → puste
    - meta.status → idle
    - meta.updated → teraz
    Informacje do segregacji przez SKILL muszą być zebrane PRZED wywołaniem tej funkcji.
    """
    sections = read_plan()
    text = _read(PLAN_FILE)

    text = _replace_section(text, "next", "")
    text = _replace_section(text, "done", "")
    text = _replace_section(text, "current", "")
    text = _replace_section(text, "blockers", "")

    meta_lines = sections.get("meta", "").splitlines()
    new_meta: list[str] = []
    for line in meta_lines:
        if line.strip().startswith("- status:"):
            line = "- status: idle"
        if line.strip().startswith("- updated:"):
            line = f"- updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        new_meta.append(line)
    text = _replace_section(text, "meta", "\n".join(new_meta))

    _write(PLAN_FILE, text)


def append_session_log(entry: str) -> None:
    """Dodaje wpis do session_log w PLAN.md."""
    sections = read_plan()
    log = sections.get("session_log", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_log = f"{log}\n- {timestamp} | {entry}".strip()
    update_plan_section("session_log", new_log)


def read_current() -> dict[str, str]:
    """Parsuje sekcję 'current' jako słownik {task, file, started}."""
    sections = read_plan()
    result: dict[str, str] = {}
    for line in sections.get("current", "").splitlines():
        line = line.strip()
        if line.startswith("- ") and ": " in line:
            key, _, val = line[2:].partition(": ")
            result[key.strip()] = val.strip()
    return result


def write_current(task: str, file: str, started: str | None = None) -> None:
    """Nadpisuje sekcję 'current' nowymi wartościami."""
    if started is None:
        started = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"- task: {task}\n- file: {file}\n- started: {started}"
    update_plan_section("current", body)


def append_rotating(section: str, item: str, max: int = 10) -> None:
    """Dodaje item do sekcji, utrzymując max ostatnich wpisów (FIFO)."""
    sections = read_plan()
    lines = [l for l in sections.get(section, "").splitlines() if l.strip()]
    lines.append(item)
    if len(lines) > max:
        lines = lines[-max:]
    update_plan_section(section, "\n".join(lines))


def append_decision(description: str, reason: str, done: bool = False,
                    arch_file: Path | None = None) -> None:
    """
    Append-only zapis decyzji do ARCHITECTURE/decisions.
    Jedyny dozwolony zapis do ARCHITECTURE.md w trakcie rundy — przez kontroler, nie agenta.

    Format: - [x/space] description | YYYY-MM-DD | reason
    Raises ValueError jeśli description lub reason są puste.
    """
    if not description.strip():
        raise ValueError("Opis decyzji nie może być pusty.")
    if not reason.strip():
        raise ValueError("Uzasadnienie decyzji nie może być puste.")

    target = arch_file if arch_file is not None else ARCHITECTURE_FILE
    text = target.read_text(encoding="utf-8")

    date_str = datetime.now().strftime("%Y-%m-%d")
    marker = "x" if done else " "
    new_line = f"- [{marker}] {description.strip()} | {date_str} | {reason.strip()}"

    # Walidacja formatu przed zapisem
    if not DECISION_LINE_RE.match(new_line):
        raise ValueError(f"Wygenerowana linia nie pasuje do formatu decisions: {new_line!r}")

    existing = _parse_sections(text).get("decisions", "").rstrip()
    new_body = f"{existing}\n{new_line}".strip()
    updated = _replace_section(text, "decisions", new_body)

    # Bezpośredni zapis — ARCHITECTURE.md jest chroniony przez _write(),
    # ale append_decision() jest jedynym autoryzowanym wyjątkiem przez kontroler.
    target.write_text(updated, encoding="utf-8")


def validate_decision_format(line: str) -> bool:
    """Zwraca True jeśli linia pasuje do formatu decisions."""
    return bool(DECISION_LINE_RE.match(line.strip()))


def validate_plan() -> list[str]:
    """
    Sprawdza integralność PLAN.md.
    Zwraca listę błędów (pusta = OK).
    """
    errors: list[str] = []
    try:
        sections = read_plan()
    except Exception as e:
        return [f"Nie można sparsować PLAN.md: {e}"]

    required = {"meta", "current", "next", "done", "blockers", "session_log"}
    missing = required - sections.keys()
    if missing:
        errors.append(f"Brakujące sekcje: {', '.join(sorted(missing))}")

    meta = sections.get("meta", "")
    if "status:" not in meta:
        errors.append("Sekcja meta nie zawiera pola 'status'.")
    if "goal:" not in meta:
        errors.append("Sekcja meta nie zawiera pola 'goal'.")

    return errors
