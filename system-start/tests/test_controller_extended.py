"""
Testy rozszerzeń controller.py: read_current, write_current, append_rotating.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.controller as ctrl
from src.controller import (
    read_current,
    write_current,
    append_rotating,
    PLAN_FILE,
)

SAMPLE_PLAN = """\
<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: Test
- session: 1
- updated: 2026-04-24 10:00
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: Stare zadanie
- file: src/old.py
- started: 2026-04-24 09:00
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
- [ ] Task X
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- entry 1
- entry 2
<!-- /SECTION:session_log -->
"""


def setup_plan(tmp_path: Path) -> Path:
    p = tmp_path / "PLAN.md"
    p.write_text(SAMPLE_PLAN, encoding="utf-8")
    ctrl.PLAN_FILE = p
    return p


def restore():
    ctrl.PLAN_FILE = PLAN_FILE


# ---------------------------------------------------------------------------
# read_current
# ---------------------------------------------------------------------------

def test_read_current_returns_dict(tmp_path):
    setup_plan(tmp_path)
    c = read_current()
    assert c["task"] == "Stare zadanie"
    assert c["file"] == "src/old.py"
    assert c["started"] == "2026-04-24 09:00"
    restore()


def test_read_current_empty_section(tmp_path):
    p = tmp_path / "PLAN.md"
    p.write_text(SAMPLE_PLAN.replace(
        "- task: Stare zadanie\n- file: src/old.py\n- started: 2026-04-24 09:00", ""
    ), encoding="utf-8")
    ctrl.PLAN_FILE = p
    c = read_current()
    assert c == {}
    restore()


# ---------------------------------------------------------------------------
# write_current
# ---------------------------------------------------------------------------

def test_write_current_updates_section(tmp_path):
    setup_plan(tmp_path)
    write_current(task="Nowe zadanie", file="src/new.py")
    c = read_current()
    assert c["task"] == "Nowe zadanie"
    assert c["file"] == "src/new.py"
    restore()


def test_write_current_custom_started(tmp_path):
    setup_plan(tmp_path)
    write_current(task="T", file="f.py", started="2026-01-01 00:00")
    c = read_current()
    assert c["started"] == "2026-01-01 00:00"
    restore()


# ---------------------------------------------------------------------------
# append_rotating
# ---------------------------------------------------------------------------

def test_append_rotating_adds_entry(tmp_path):
    setup_plan(tmp_path)
    append_rotating("session_log", "- nowy wpis", max=10)
    from src.controller import read_plan
    sections = read_plan()
    assert "nowy wpis" in sections["session_log"]
    restore()


def test_append_rotating_respects_max(tmp_path):
    setup_plan(tmp_path)
    for i in range(15):
        append_rotating("session_log", f"- wpis {i}", max=5)
    from src.controller import read_plan
    sections = read_plan()
    lines = [l for l in sections["session_log"].splitlines() if l.strip()]
    assert len(lines) <= 5
    restore()


def test_append_rotating_keeps_latest(tmp_path):
    setup_plan(tmp_path)
    for i in range(7):
        append_rotating("session_log", f"- wpis {i}", max=5)
    from src.controller import read_plan
    sections = read_plan()
    assert "wpis 6" in sections["session_log"]
    assert "wpis 0" not in sections["session_log"]
    restore()
