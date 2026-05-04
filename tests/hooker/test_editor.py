"""Testy dla src/hooker/core/editor.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.hooker.core.editor import (
    apply_hooks,
    hooks_to_section,
    load_hooks_for_type,
    read_settings,
)
from src.hooker.core.model import Hook, HookLevel, HookType

FIXTURES = Path(__file__).parent / "fixtures"


def _h(command: str, matcher: str = "", level: HookLevel = HookLevel.GLOBAL) -> Hook:
    return Hook(
        hook_type=HookType.PRE_TOOL_USE,
        command=command,
        matcher=matcher,
        source_file=Path("fake"),
        level=level,
    )


# ---- read_settings ----

def test_read_settings_existing_file():
    data = read_settings(FIXTURES / "global_real.json")
    assert isinstance(data, dict)


def test_read_settings_nonexistent():
    data = read_settings(Path("nonexistent_xyz.json"))
    assert data == {}


def test_read_settings_malformed():
    data = read_settings(FIXTURES / "edge_malformed.json")
    assert data == {}


def test_read_settings_empty_object():
    data = read_settings(FIXTURES / "edge_empty.json")
    assert data == {}


# ---- hooks_to_section ----

def test_hooks_to_section_single_no_matcher():
    hooks = [_h("echo hello")]
    section = hooks_to_section(hooks)
    assert len(section) == 1
    assert "matcher" not in section[0]
    assert section[0]["hooks"] == [{"type": "command", "command": "echo hello"}]


def test_hooks_to_section_single_with_matcher():
    hooks = [_h("logger.sh", "Bash")]
    section = hooks_to_section(hooks)
    assert section[0]["matcher"] == "Bash"


def test_hooks_to_section_groups_same_matcher():
    hooks = [_h("a.sh", "Bash"), _h("b.sh", "Bash")]
    section = hooks_to_section(hooks)
    assert len(section) == 1
    assert len(section[0]["hooks"]) == 2


def test_hooks_to_section_different_matchers():
    hooks = [_h("a.sh", "Bash"), _h("b.sh", "Read")]
    section = hooks_to_section(hooks)
    assert len(section) == 2


def test_hooks_to_section_empty():
    assert hooks_to_section([]) == []


# ---- apply_hooks ----

def test_apply_hooks_adds_to_empty_settings():
    hooks = [_h("echo ok")]
    updated = apply_hooks({}, HookType.PRE_TOOL_USE, hooks)
    assert "hooks" in updated
    assert "PreToolUse" in updated["hooks"]


def test_apply_hooks_preserves_other_keys():
    settings = {"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}
    hooks = [_h("echo ok")]
    updated = apply_hooks(settings, HookType.PRE_TOOL_USE, hooks)
    assert updated["model"] == "opus"
    assert "Stop" in updated["hooks"]
    assert "PreToolUse" in updated["hooks"]


def test_apply_hooks_removes_type_when_empty():
    settings = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]}}
    updated = apply_hooks(settings, HookType.PRE_TOOL_USE, [])
    assert "PreToolUse" not in updated.get("hooks", {})


def test_apply_hooks_removes_hooks_key_when_all_empty():
    settings = {"hooks": {"PreToolUse": []}}
    updated = apply_hooks(settings, HookType.PRE_TOOL_USE, [])
    assert "hooks" not in updated


def test_apply_hooks_roundtrip(tmp_path):
    """Zapis i odczyt przez persister + parser daje ten sam hook."""
    from src.hooker.core.persister import write_settings
    from src.hooker.core.parser import parse_settings

    target = tmp_path / "settings.json"
    hooks = [_h("python hook.py", "Bash")]
    settings = apply_hooks({}, HookType.PRE_TOOL_USE, hooks)
    write_settings(target, settings)

    parsed = parse_settings(target, HookLevel.GLOBAL)
    assert len(parsed) == 1
    assert parsed[0].command == "python hook.py"
    assert parsed[0].matcher == "Bash"


# ---- load_hooks_for_type ----

def test_load_hooks_for_type_global_real():
    hooks = load_hooks_for_type(
        FIXTURES / "global_real.json",
        HookType.PRE_TOOL_USE,
        HookLevel.GLOBAL,
    )
    assert all(h.hook_type == HookType.PRE_TOOL_USE for h in hooks)


def test_load_hooks_for_type_returns_only_requested_type():
    hooks = load_hooks_for_type(
        FIXTURES / "global_real.json",
        HookType.STOP,
        HookLevel.GLOBAL,
    )
    assert all(h.hook_type == HookType.STOP for h in hooks)


def test_load_hooks_for_type_nonexistent():
    hooks = load_hooks_for_type(
        Path("nonexistent.json"),
        HookType.PRE_TOOL_USE,
        HookLevel.GLOBAL,
    )
    assert hooks == []
