"""
SKILL Agent — orchestracja operacji na PLAN.md przez Python Controller.
Każda funkcja pcc_* to jeden SKILL wywoływany przez agenta.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.logger import get_logger as _get_logger
_log = _get_logger("skill")

from src.controller import (
    read_plan,
    read_current,
    write_current,
    mark_task_done,
    append_rotating,
    update_plan_section,
    flush_plan,
    validate_plan,
    append_decision,
)


def pcc_status() -> str:
    """
    SKILL: pcc-status
    Zwraca krótki raport: gdzie jestem (current) + ostatni wpis session_log.
    """
    sections = read_plan()
    current = read_current()

    task = current.get("task", "brak")
    file = current.get("file", "brak")
    started = current.get("started", "brak")

    log_lines = [l for l in sections.get("session_log", "").splitlines() if l.strip()]
    last_log = log_lines[-1] if log_lines else "brak wpisów"

    next_lines = [l for l in sections.get("next", "").splitlines() if l.strip()]
    next_count = len(next_lines)

    return (
        f"=== PCC Status ===\n"
        f"Current task : {task}\n"
        f"File         : {file}\n"
        f"Started      : {started}\n"
        f"Next in queue: {next_count} zadań\n"
        f"Last log     : {last_log}\n"
        f"Meta status  : {_meta_field(sections, 'status')}"
    )


def pcc_step_done(timestamp: str | None = None) -> str:
    """
    SKILL: pcc-step-done
    Przenosi current → done z timestampem, pop next[0] → current.
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = read_plan()
    current = read_current()
    task = current.get("task", "")
    file = current.get("file", "")

    if not task:
        return "ERROR: sekcja current jest pusta — nie ma czego zamknąć."

    done_lines = [l for l in sections.get("done", "").splitlines() if l.strip()]
    done_lines.append(f"- [x] {task} ({file}) @ {timestamp}")

    next_lines = [l for l in sections.get("next", "").splitlines() if l.strip()]

    text_plan = Path(__file__).resolve().parent.parent / "PLAN.md"
    from src.controller import _read, _replace_section, _write, PLAN_FILE
    text = _read(PLAN_FILE)
    text = _replace_section(text, "done", "\n".join(done_lines))

    if next_lines:
        new_task_line = next_lines.pop(0)
        new_task = new_task_line.lstrip("- [ ]").strip()
        new_current = f"- task: {new_task}\n- file: \n- started: {timestamp}"
        text = _replace_section(text, "current", new_current)
        text = _replace_section(text, "next", "\n".join(next_lines))
    else:
        text = _replace_section(text, "current", "")

    _write(PLAN_FILE, text)

    log_entry = f"- {timestamp} | step-done: {task}"
    from src.controller import _parse_sections
    sections2 = _parse_sections(text)
    log_lines = [l for l in sections2.get("session_log", "").splitlines() if l.strip()]
    log_lines.append(log_entry)
    if len(log_lines) > 10:
        log_lines = log_lines[-10:]
    text = _replace_section(text, "session_log", "\n".join(log_lines))
    _write(PLAN_FILE, text)

    return f"OK: '{task}' → done. Nowe current: {next_lines[0] if False else 'z kolejki lub puste'}."


def pcc_step_start(task: str, file: str = "") -> str:
    """
    SKILL: pcc-step-start
    Użytkownik mówi co robi — zapisuje do PLAN/current.
    """
    started = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_current(task=task, file=file, started=started)
    append_rotating(
        "session_log",
        f"- {started} | step-start: {task}",
        max=10,
    )
    return f"OK: current ustawiony na '{task}' ({file}) @ {started}."


def pcc_decision(description: str, reason: str, done: bool = False) -> str:
    """
    SKILL: pcc-decision
    Claude chce zapisać decyzję architektoniczną — trafia do ARCHITECTURE/decisions.
    Jedyna autoryzowana ścieżka zapisu do ARCHITECTURE.md w trakcie rundy.

    Args:
        description: co zdecydowano (np. "użyć data_sources.query zamiast databases.query")
        reason: dlaczego (np. "notion-client 3.0.0 usunął databases.query")
        done: czy decyzja już wdrożona ([x]) czy planowana ([ ])
    """
    try:
        append_decision(description=description, reason=reason, done=done)
        marker = "x" if done else " "
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        append_rotating(
            "session_log",
            f"- {ts} | decision: [{marker}] {description[:60]}",
            max=10,
        )
        return f"OK: decyzja zapisana do ARCHITECTURE/decisions."
    except ValueError as e:
        return f"ERROR: {e}"


def pcc_round_end(notion_sync: bool = True) -> str:
    """
    SKILL: pcc-round-end
    Zbiera done items, czyści PLAN.md, opcjonalnie pushuje do Notion.
    """
    errors = validate_plan()
    if errors:
        return "BLOKADA: walidacja nie przeszła:\n" + "\n".join(errors)

    sections = read_plan()
    done_items = [l for l in sections.get("done", "").splitlines() if l.strip()]
    log_items = [l for l in sections.get("session_log", "").splitlines() if l.strip()]

    summary = "=== Round End Summary ===\nDone items (do migracji przez SKILL):\n"
    summary += "\n".join(done_items) if done_items else "  (brak)"
    summary += "\n\nSession log:\n"
    summary += "\n".join(log_items) if log_items else "  (brak)"

    # Push do Notion PRZED wyczyszczeniem PLAN.md
    if notion_sync:
        try:
            from src.notion_sync import sync
            from src.controller import PLAN_FILE
            urls = sync(project_dir=PLAN_FILE.parent)
            summary += "\n\nNotion sync OK:\n"
            summary += "\n".join(f"  {f} -> {u}" for f, u in urls.items())
            _log.info("pcc_round_end: notion sync OK | %d plikow", len(urls))
        except Exception as e:
            summary += f"\n\nNotion sync BLAD (kontynuuje): {e}"
            _log.error("pcc_round_end: notion sync BLAD | %s", e)

    flush_plan()
    _log.info("pcc_round_end: PLAN.md wyczyszczony | done=%d", len(done_items))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    append_rotating("session_log", f"- {timestamp} | round-end: PLAN wyczyszczony", max=10)

    return summary


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _meta_field(sections: dict[str, str], field: str) -> str:
    for line in sections.get("meta", "").splitlines():
        line = line.strip()
        if line.startswith(f"- {field}:"):
            return line.split(":", 1)[1].strip()
    return "brak"
