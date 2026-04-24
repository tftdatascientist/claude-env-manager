"""
Testy CLAUDE.md update rule:
  - append_decision() w controller.py
  - pcc_decision() w skill.py
  - validate_decision_format()
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.controller import append_decision, validate_decision_format, ARCHITECTURE_FILE
from src.skill import pcc_decision

SAMPLE_ARCH = """\
<!-- ARCHITECTURE v1.1 -->

## Decisions
<!-- SECTION:decisions -->
- [x] skrypt Python jako jedyny zapis do MD | 2026-04-24 | eliminuje niespójności
<!-- /SECTION:decisions -->

## Constraints
<!-- SECTION:constraints -->
- skrypt Python musi zakończyć się sukcesem
<!-- /SECTION:constraints -->
"""


def setup_arch(tmp_path: Path) -> Path:
    p = tmp_path / "ARCHITECTURE.md"
    p.write_text(SAMPLE_ARCH, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# validate_decision_format
# ---------------------------------------------------------------------------

def test_valid_decision_format():
    assert validate_decision_format("- [x] coś zrobiono | 2026-04-24 | bo tak")
    assert validate_decision_format("- [ ] plan na jutro | 2026-04-24 | potrzeba")


def test_invalid_decision_format_missing_pipes():
    assert not validate_decision_format("- [x] brak daty i powodu")


def test_invalid_decision_format_wrong_date():
    assert not validate_decision_format("- [x] opis | 24-04-2026 | powód")


def test_invalid_decision_format_no_marker():
    assert not validate_decision_format("- opis | 2026-04-24 | powód")


# ---------------------------------------------------------------------------
# append_decision
# ---------------------------------------------------------------------------

def test_append_decision_adds_line(tmp_path):
    arch = setup_arch(tmp_path)
    append_decision("użyć data_sources.query", "notion-client 3.0.0", done=True, arch_file=arch)
    text = arch.read_text(encoding="utf-8")
    assert "użyć data_sources.query" in text
    assert "notion-client 3.0.0" in text
    assert "- [x]" in text


def test_append_decision_preserves_existing(tmp_path):
    arch = setup_arch(tmp_path)
    append_decision("nowa decyzja", "nowy powód", arch_file=arch)
    text = arch.read_text(encoding="utf-8")
    # stara decyzja nadal tam
    assert "skrypt Python jako jedyny zapis do MD" in text
    # nowa dopisana
    assert "nowa decyzja" in text


def test_append_decision_unfinished_marker(tmp_path):
    arch = setup_arch(tmp_path)
    append_decision("plan jeszcze nie wdrożony", "czekamy", done=False, arch_file=arch)
    text = arch.read_text(encoding="utf-8")
    assert "- [ ] plan jeszcze nie wdrożony" in text


def test_append_decision_empty_description_raises(tmp_path):
    arch = setup_arch(tmp_path)
    with pytest.raises(ValueError):
        append_decision("", "powód", arch_file=arch)


def test_append_decision_empty_reason_raises(tmp_path):
    arch = setup_arch(tmp_path)
    with pytest.raises(ValueError):
        append_decision("opis", "", arch_file=arch)


def test_append_decision_does_not_touch_other_sections(tmp_path):
    arch = setup_arch(tmp_path)
    append_decision("decyzja X", "powód Y", arch_file=arch)
    text = arch.read_text(encoding="utf-8")
    assert "skrypt Python musi zakończyć się sukcesem" in text


def test_append_multiple_decisions(tmp_path):
    arch = setup_arch(tmp_path)
    append_decision("decyzja A", "powód A", arch_file=arch)
    append_decision("decyzja B", "powód B", arch_file=arch)
    text = arch.read_text(encoding="utf-8")
    assert "decyzja A" in text
    assert "decyzja B" in text


# ---------------------------------------------------------------------------
# pcc_decision (skill)
# ---------------------------------------------------------------------------

def test_pcc_decision_returns_ok(tmp_path, monkeypatch):
    import src.controller as ctrl
    arch = setup_arch(tmp_path)
    plan = tmp_path / "PLAN.md"
    plan.write_text("""\
<!-- PLAN v2.0 -->
## Session Log
<!-- SECTION:session_log -->
<!-- /SECTION:session_log -->
""", encoding="utf-8")

    original_arch = ctrl.ARCHITECTURE_FILE
    original_plan = ctrl.PLAN_FILE
    ctrl.ARCHITECTURE_FILE = arch
    ctrl.PLAN_FILE = plan

    result = pcc_decision("użyć typer zamiast argparse", "lepszy DX", done=True)
    assert "OK" in result
    assert "użyć typer zamiast argparse" in arch.read_text(encoding="utf-8")

    ctrl.ARCHITECTURE_FILE = original_arch
    ctrl.PLAN_FILE = original_plan


def test_pcc_decision_returns_error_on_empty(tmp_path, monkeypatch):
    import src.controller as ctrl
    arch = setup_arch(tmp_path)
    plan = tmp_path / "PLAN.md"
    plan.write_text("""\
<!-- PLAN v2.0 -->
## Session Log
<!-- SECTION:session_log -->
<!-- /SECTION:session_log -->
""", encoding="utf-8")

    ctrl.ARCHITECTURE_FILE = arch
    ctrl.PLAN_FILE = plan

    result = pcc_decision("", "powód")
    assert "ERROR" in result

    import src.controller as ctrl2
    ctrl2.ARCHITECTURE_FILE = ctrl.BASE_DIR / "ARCHITECTURE.md"
    ctrl2.PLAN_FILE = ctrl.BASE_DIR / "PLAN.md"
