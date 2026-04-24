"""
Test template_parser — weryfikuje czy wygenerowany PLAN.md z szablonu parsuje się poprawnie.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.controller import _parse_sections

REQUIRED_SECTIONS = {"meta", "current", "next", "done", "blockers", "session_log"}

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "plan_template.md"


def test_template_file_exists():
    assert TEMPLATE_PATH.exists(), "templates/plan_template.md nie istnieje"


def test_template_has_all_sections():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    sections = _parse_sections(text)
    missing = REQUIRED_SECTIONS - sections.keys()
    assert not missing, f"Brakujące sekcje w szablonie: {missing}"


def test_template_sections_not_empty_after_fill():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    filled = (
        text
        .replace("{{GOAL}}", "Test celu")
        .replace("{{SESSION}}", "1")
        .replace("{{UPDATED}}", "2026-04-24 10:00")
        .replace("{{CURRENT_TASK}}", "Test task")
        .replace("{{CURRENT_FILE}}", "src/test.py")
        .replace("{{STARTED}}", "2026-04-24 10:00")
    )
    sections = _parse_sections(filled)
    assert "Test celu" in sections["meta"]
    assert "Test task" in sections["current"]


def test_template_meta_fields():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    sections = _parse_sections(text)
    meta = sections["meta"]
    assert "status:" in meta
    assert "goal:" in meta
    assert "session:" in meta
    assert "updated:" in meta


def test_template_current_fields():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    sections = _parse_sections(text)
    current = sections["current"]
    assert "task:" in current
    assert "file:" in current
    assert "started:" in current
