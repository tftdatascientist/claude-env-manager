"""
Test end-to-end: symulacja pełnego cyklu sesji CC.
Otwieramy PLAN, ustawiamy current, kończymy step, zamykamy rundę.
Weryfikujemy deterministyczność każdego kroku.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.controller as ctrl
from src.controller import PLAN_FILE, validate_plan
from src.skill import pcc_status, pcc_step_start, pcc_step_done, pcc_round_end


FRESH_PLAN = """\
<!-- PLAN v2.0 -->

## Meta
<!-- SECTION:meta -->
- status: active
- goal: E2E test goal
- session: 99
- updated: 2026-04-24 00:00
<!-- /SECTION:meta -->

## Current
<!-- SECTION:current -->
- task:
- file:
- started:
<!-- /SECTION:current -->

## Next
<!-- SECTION:next -->
- [ ] Zadanie Alpha
- [ ] Zadanie Beta
<!-- /SECTION:next -->

## Done
<!-- SECTION:done -->
<!-- /SECTION:done -->

## Blockers
<!-- SECTION:blockers -->
<!-- /SECTION:blockers -->

## Session Log
<!-- SECTION:session_log -->
- 2026-04-24 00:00 | start
<!-- /SECTION:session_log -->
"""


def setup(tmp_path: Path) -> None:
    p = tmp_path / "PLAN.md"
    p.write_text(FRESH_PLAN, encoding="utf-8")
    ctrl.PLAN_FILE = p


def restore():
    ctrl.PLAN_FILE = PLAN_FILE


def test_e2e_full_cycle(tmp_path):
    setup(tmp_path)

    # 1. status na starcie
    status = pcc_status()
    assert "E2E test goal" in status or "brak" in status

    # 2. step-start — użytkownik zaczyna Zadanie Alpha
    result = pcc_step_start("Zadanie Alpha", "src/alpha.py")
    assert "OK" in result
    c = ctrl.read_current()
    assert c["task"] == "Zadanie Alpha"
    assert c["file"] == "src/alpha.py"

    # 3. step-done — Alpha skończona, Beta powinna wejść do current
    result = pcc_step_done()
    assert "OK" in result or "step-done" in result

    from src.controller import _parse_sections, _read
    text = _read(ctrl.PLAN_FILE)
    sections = _parse_sections(text)
    done = sections["done"]
    assert "Zadanie Alpha" in done or "alpha" in done.lower()

    # 4. step-start Zadanie Beta
    pcc_step_start("Zadanie Beta", "src/beta.py")
    c2 = ctrl.read_current()
    assert c2["task"] == "Zadanie Beta"

    # 5. round-end — czyści PLAN (Notion sync wyłączony w testach)
    summary = pcc_round_end(notion_sync=False)
    assert "Round End" in summary

    from src.controller import read_plan
    sections2 = read_plan()
    assert sections2["next"].strip() == ""
    assert sections2["done"].strip() == ""
    assert sections2["current"].strip() == ""
    assert "idle" in sections2["meta"]

    restore()


def test_e2e_validate_after_each_step(tmp_path):
    setup(tmp_path)

    errors = validate_plan()
    assert errors == [], f"Błędy po starcie: {errors}"

    pcc_step_start("Zadanie Alpha", "src/alpha.py")
    errors = validate_plan()
    assert errors == [], f"Błędy po step-start: {errors}"

    pcc_step_done()
    errors = validate_plan()
    assert errors == [], f"Błędy po step-done: {errors}"

    restore()
