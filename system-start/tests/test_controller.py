"""
Testy jednostkowe dla src/controller.py.
Używają tmp_path — nie dotykają rzeczywistego PLAN.md.
"""
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.controller import (
    _parse_sections,
    _replace_section,
    read_plan,
    update_plan_section,
    mark_task_done,
    flush_plan,
    validate_plan,
    append_session_log,
    PLAN_FILE,
    PROTECTED_FILES,
    _write,
)


SAMPLE_PLAN = """\
<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: Test goal
- session: 1
- updated: 2026-04-24 01:00
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task: Some task
- file: src/foo.py
- started: 2026-04-24 01:00
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
- [ ] Task A
- [ ] Task B
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- session:1 | 2026-04-24 | init
<!-- /SECTION:session_log -->
"""


@pytest.fixture()
def plan_file(tmp_path: Path) -> Path:
    p = tmp_path / "PLAN.md"
    p.write_text(SAMPLE_PLAN, encoding="utf-8")
    return p


def use_plan(plan_file: Path):
    """Przekierowuje stałą PLAN_FILE na plik tymczasowy."""
    import src.controller as ctrl
    original = ctrl.PLAN_FILE
    ctrl.PLAN_FILE = plan_file
    yield
    ctrl.PLAN_FILE = original


# ---------------------------------------------------------------------------
# _parse_sections
# ---------------------------------------------------------------------------

def test_parse_sections_returns_all_keys():
    sections = _parse_sections(SAMPLE_PLAN)
    assert set(sections) == {"meta", "current", "next", "done", "blockers", "session_log"}


def test_parse_sections_next_contains_tasks():
    sections = _parse_sections(SAMPLE_PLAN)
    assert "Task A" in sections["next"]
    assert "Task B" in sections["next"]


# ---------------------------------------------------------------------------
# _replace_section
# ---------------------------------------------------------------------------

def test_replace_section_changes_content():
    updated = _replace_section(SAMPLE_PLAN, "done", "- [x] Finished something")
    assert "Finished something" in updated
    assert "<!-- SECTION:done -->" in updated


def test_replace_section_missing_raises():
    with pytest.raises(ValueError, match="nie istnieje"):
        _replace_section(SAMPLE_PLAN, "nonexistent", "body")


# ---------------------------------------------------------------------------
# _write protection
# ---------------------------------------------------------------------------

def test_write_blocks_protected_files(tmp_path: Path):
    for name in PROTECTED_FILES:
        p = tmp_path / name
        p.write_text("x", encoding="utf-8")
        with pytest.raises(PermissionError):
            _write(p, "overwrite attempt")


def test_write_allows_plan(tmp_path: Path):
    p = tmp_path / "PLAN.md"
    p.write_text("old", encoding="utf-8")
    _write(p, "new content")
    assert p.read_text(encoding="utf-8") == "new content"


# ---------------------------------------------------------------------------
# read_plan / update_plan_section
# ---------------------------------------------------------------------------

def test_read_plan_via_fixture(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    sections = read_plan()
    assert "active" in sections["meta"]
    ctrl.PLAN_FILE = PLAN_FILE  # restore


def test_update_plan_section(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    update_plan_section("blockers", "- brak internetu")
    text = plan_file.read_text(encoding="utf-8")
    assert "brak internetu" in text
    ctrl.PLAN_FILE = PLAN_FILE


# ---------------------------------------------------------------------------
# mark_task_done
# ---------------------------------------------------------------------------

def test_mark_task_done_moves_task(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    mark_task_done("Task A")
    text = plan_file.read_text(encoding="utf-8")
    assert "- [x] Task A" in text
    assert "- [ ] Task A" not in text
    ctrl.PLAN_FILE = PLAN_FILE


def test_mark_task_done_missing_raises(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    with pytest.raises(ValueError, match="nie znalezione"):
        mark_task_done("Nonexistent task")
    ctrl.PLAN_FILE = PLAN_FILE


# ---------------------------------------------------------------------------
# flush_plan
# ---------------------------------------------------------------------------

def test_flush_plan_clears_sections(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    flush_plan()
    sections = _parse_sections(plan_file.read_text(encoding="utf-8"))
    assert sections["next"].strip() == ""
    assert sections["done"].strip() == ""
    assert sections["current"].strip() == ""
    assert "idle" in sections["meta"]
    ctrl.PLAN_FILE = PLAN_FILE


# ---------------------------------------------------------------------------
# validate_plan
# ---------------------------------------------------------------------------

def test_validate_plan_ok(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    errors = validate_plan()
    assert errors == []
    ctrl.PLAN_FILE = PLAN_FILE


def test_validate_plan_missing_section(tmp_path: Path):
    import src.controller as ctrl
    broken = tmp_path / "PLAN.md"
    broken.write_text("<!-- SECTION:meta -->\n- status: active\n<!-- /SECTION:meta -->", encoding="utf-8")
    ctrl.PLAN_FILE = broken
    errors = validate_plan()
    assert any("Brakujące" in e for e in errors)
    ctrl.PLAN_FILE = PLAN_FILE


# ---------------------------------------------------------------------------
# append_session_log
# ---------------------------------------------------------------------------

def test_append_session_log(plan_file: Path):
    import src.controller as ctrl
    ctrl.PLAN_FILE = plan_file
    append_session_log("test entry xyz")
    text = plan_file.read_text(encoding="utf-8")
    assert "test entry xyz" in text
    ctrl.PLAN_FILE = PLAN_FILE
