"""Testy parsera settings.json → List[Hook]."""

from pathlib import Path

import pytest

from src.hooker.core.model import HookLevel, HookType
from src.hooker.core.parser import parse_settings

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_global_real():
    hooks = parse_settings(FIXTURES / "global_real.json", HookLevel.GLOBAL)
    assert len(hooks) == 6
    types = {h.hook_type for h in hooks}
    assert HookType.PRE_TOOL_USE in types
    assert HookType.POST_TOOL_USE in types
    assert HookType.STOP in types
    assert HookType.NOTIFICATION in types
    assert HookType.USER_PROMPT_SUBMIT in types
    for h in hooks:
        assert h.level == HookLevel.GLOBAL
        assert h.source_file == FIXTURES / "global_real.json"
        assert h.command


def test_parse_global_real_matchers():
    hooks = parse_settings(FIXTURES / "global_real.json", HookLevel.GLOBAL)
    pre = [h for h in hooks if h.hook_type == HookType.PRE_TOOL_USE]
    assert len(pre) == 1
    assert "Bash" in pre[0].matcher


def test_parse_project_local_sss():
    hooks = parse_settings(FIXTURES / "project_local_sss.json", HookLevel.PROJECT)
    assert len(hooks) == 2
    types = {h.hook_type for h in hooks}
    assert HookType.POST_TOOL_USE in types
    assert HookType.USER_PROMPT_SUBMIT in types
    for h in hooks:
        assert h.level == HookLevel.PROJECT


def test_parse_edge_no_matcher():
    hooks = parse_settings(FIXTURES / "edge_no_matcher.json", HookLevel.PROJECT)
    assert len(hooks) == 2
    for h in hooks:
        assert h.matcher == ""


def test_parse_edge_empty():
    hooks = parse_settings(FIXTURES / "edge_empty.json", HookLevel.GLOBAL)
    assert hooks == []


def test_parse_edge_malformed():
    hooks = parse_settings(FIXTURES / "edge_malformed.json", HookLevel.GLOBAL)
    assert hooks == []


def test_parse_nonexistent_file():
    hooks = parse_settings(Path("/nonexistent/settings.json"), HookLevel.GLOBAL)
    assert hooks == []


def test_parse_stop_two_hooks():
    """Stop ma 2 wpisy w global_real — obie muszą być sparsowane."""
    hooks = parse_settings(FIXTURES / "global_real.json", HookLevel.GLOBAL)
    stop_hooks = [h for h in hooks if h.hook_type == HookType.STOP]
    assert len(stop_hooks) == 2
