"""Tests for src/projektant/template_parser.py"""
import pytest
from pathlib import Path
from textwrap import dedent

from src.projektant.template_parser import (
    read_section,
    write_section,
    parse_dict,
    build_dict,
    parse_list,
    build_list,
    create_from_template,
    status_bump_session,
    status_touch,
    status_move_to_done,
    plan_check_step,
    plan_set_status,
    read_section_dict,
    read_section_list,
    update_section_dict,
    update_section_list,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TEXT = dedent("""\
    ## Meta
    <!-- SECTION:meta -->
    - project: TestProject
    - session: 3
    - updated: 2026-01-01 12:00
    - plan: none
    <!-- /SECTION:meta -->

    ## Done
    <!-- SECTION:done -->
    - [x] Task A | 2026-01-01
    <!-- /SECTION:done -->

    ## Current
    <!-- SECTION:current -->
    - task: Fix bug
    - files: src/foo.py
    - state: in progress
    - blocker: none
    - next_step: run tests
    <!-- /SECTION:current -->

    ## Next
    <!-- SECTION:next -->
    - [ ] Implement feature X
    - [ ] Write docs | 2026-02-01
    <!-- /SECTION:next -->
""")


# ---------------------------------------------------------------------------
# read_section / write_section
# ---------------------------------------------------------------------------

def test_read_section_found():
    body = read_section(SAMPLE_TEXT, "meta")
    assert "project: TestProject" in body


def test_read_section_not_found():
    assert read_section(SAMPLE_TEXT, "nonexistent") is None


def test_write_section_replaces_body():
    new_body = "- project: NewProject\n- session: 1\n"
    result = write_section(SAMPLE_TEXT, "meta", new_body)
    assert "NewProject" in result
    assert "TestProject" not in result


def test_write_section_missing_raises():
    with pytest.raises(ValueError):
        write_section(SAMPLE_TEXT, "missing_section", "body\n")


# ---------------------------------------------------------------------------
# parse_dict / build_dict
# ---------------------------------------------------------------------------

def test_parse_dict_basic():
    body = "- key1: value1\n- key2: value two\n"
    result = parse_dict(body)
    assert result == {"key1": "value1", "key2": "value two"}


def test_parse_dict_empty_value():
    body = "- key: \n"
    result = parse_dict(body)
    assert result["key"] == ""


def test_parse_dict_empty_body():
    assert parse_dict("") == {}


def test_build_dict_roundtrip():
    data = {"a": "1", "b": "hello world"}
    assert parse_dict(build_dict(data)) == data


# ---------------------------------------------------------------------------
# parse_list / build_list
# ---------------------------------------------------------------------------

def test_parse_list_basic():
    body = "- [x] Task A | 2026-01-01\n- [ ] Task B\n"
    items = parse_list(body)
    assert items[0] == {"done": True, "text": "Task A", "date": "2026-01-01"}
    assert items[1] == {"done": False, "text": "Task B", "date": ""}


def test_parse_list_empty_body():
    assert parse_list("") == []


def test_build_list_roundtrip():
    items = [
        {"done": True, "text": "Done task", "date": "2026-01-01"},
        {"done": False, "text": "Pending task", "date": ""},
    ]
    rebuilt = parse_list(build_list(items))
    assert rebuilt == items


def test_build_list_no_date():
    items = [{"done": False, "text": "No date task"}]
    result = build_list(items)
    assert "| " not in result


# ---------------------------------------------------------------------------
# File-level helpers (using tmp_path)
# ---------------------------------------------------------------------------

def test_read_write_section_dict(tmp_path):
    f = tmp_path / "STATUS.md"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    data = read_section_dict(f, "meta")
    assert data["project"] == "TestProject"

    data["project"] = "Updated"
    update_section_dict(f, "meta", data)
    assert read_section_dict(f, "meta")["project"] == "Updated"


def test_read_write_section_list(tmp_path):
    f = tmp_path / "STATUS.md"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    items = read_section_list(f, "next")
    assert len(items) == 2

    items.append({"done": False, "text": "Extra task", "date": ""})
    update_section_list(f, "next", items)
    assert len(read_section_list(f, "next")) == 3


# ---------------------------------------------------------------------------
# STATUS operations
# ---------------------------------------------------------------------------

def test_status_bump_session(tmp_path):
    f = tmp_path / "STATUS.md"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    status_bump_session(f)
    meta = read_section_dict(f, "meta")
    assert meta["session"] == "4"
    assert meta["updated"] != "2026-01-01 12:00"


def test_status_touch_updates_timestamp(tmp_path):
    f = tmp_path / "STATUS.md"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    status_touch(f)
    meta = read_section_dict(f, "meta")
    assert meta["updated"] != "2026-01-01 12:00"


def test_status_move_to_done_found(tmp_path):
    f = tmp_path / "STATUS.md"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    ok = status_move_to_done(f, "feature X")
    assert ok
    next_items = read_section_list(f, "next")
    done_items = read_section_list(f, "done")
    assert not any("feature X" in i["text"] for i in next_items)
    assert any("feature X" in i["text"] for i in done_items)


def test_status_move_to_done_not_found(tmp_path):
    f = tmp_path / "STATUS.md"
    f.write_text(SAMPLE_TEXT, encoding="utf-8")
    ok = status_move_to_done(f, "nonexistent task xyz")
    assert not ok


# ---------------------------------------------------------------------------
# PLAN operations
# ---------------------------------------------------------------------------

PLAN_TEXT = dedent("""\
    <!-- PLAN v1.0 -->

    ## Meta
    <!-- SECTION:meta -->
    - status: active
    - goal: Implement feature
    - session: 1
    - updated: 2026-01-01 12:00
    <!-- /SECTION:meta -->

    ## Steps
    <!-- SECTION:steps -->
    - [ ] Design API
    - [ ] Write tests
    - [x] Setup project | 2026-01-01
    <!-- /SECTION:steps -->

    ## Notes
    <!-- SECTION:notes -->
    <!-- /SECTION:notes -->
""")


def test_plan_check_step_found(tmp_path):
    f = tmp_path / "PLAN.md"
    f.write_text(PLAN_TEXT, encoding="utf-8")
    ok = plan_check_step(f, "Design API")
    assert ok
    steps = read_section_list(f, "steps")
    assert steps[0]["done"] is True


def test_plan_check_step_not_found(tmp_path):
    f = tmp_path / "PLAN.md"
    f.write_text(PLAN_TEXT, encoding="utf-8")
    ok = plan_check_step(f, "nonexistent step")
    assert not ok


def test_plan_set_status(tmp_path):
    f = tmp_path / "PLAN.md"
    f.write_text(PLAN_TEXT, encoding="utf-8")
    plan_set_status(f, "done")
    meta = read_section_dict(f, "meta")
    assert meta["status"] == "done"


# ---------------------------------------------------------------------------
# Template instantiation
# ---------------------------------------------------------------------------

def test_create_from_template_status(tmp_path):
    dest = tmp_path / "STATUS.md"
    create_from_template("STATUS", dest)
    assert dest.exists()
    text = dest.read_text(encoding="utf-8")
    assert "<!-- SECTION:meta -->" in text
    assert "<!-- SECTION:done -->" in text


def test_create_from_template_with_overrides(tmp_path):
    dest = tmp_path / "STATUS.md"
    create_from_template("STATUS", dest, overrides={
        "meta": {"project": "MyProject", "session": "1", "updated": "2026-04-17", "plan": "none"}
    })
    meta = read_section_dict(dest, "meta")
    assert meta["project"] == "MyProject"


def test_create_from_template_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_from_template("NONEXISTENT", tmp_path / "out.md")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_read_section_empty_section():
    text = "<!-- SECTION:empty -->\n<!-- /SECTION:empty -->"
    body = read_section(text, "empty")
    assert body == ""


def test_parse_dict_ignores_non_dict_lines():
    body = "some random text\n- key: value\n# header\n"
    result = parse_dict(body)
    assert result == {"key": "value"}


def test_parse_list_ignores_non_list_lines():
    body = "random text\n- [x] Valid task\n## header\n"
    items = parse_list(body)
    assert len(items) == 1
    assert items[0]["text"] == "Valid task"


def test_utf8_encoding(tmp_path):
    f = tmp_path / "STATUS.md"
    text = SAMPLE_TEXT.replace("TestProject", "Żółw Ślimak")
    f.write_text(text, encoding="utf-8")
    meta = read_section_dict(f, "meta")
    assert meta["project"] == "Żółw Ślimak"
