"""Testy mergera hooków global + project."""

from pathlib import Path

from src.hooker.core.model import Hook, HookLevel, HookType
from src.hooker.core.merger import merge


def _hook(hook_type: HookType, command: str, matcher: str = "", level: HookLevel = HookLevel.GLOBAL) -> Hook:
    return Hook(hook_type=hook_type, command=command, matcher=matcher,
                source_file=Path("/fake"), level=level)


def test_merge_only_global():
    gh = _hook(HookType.STOP, "echo stop")
    result = merge([gh], [])
    assert len(result.merged) == 1
    assert result.merged[0].hook == gh
    assert not result.merged[0].is_shadowed


def test_merge_only_project():
    ph = _hook(HookType.USER_PROMPT_SUBMIT, "echo submit", level=HookLevel.PROJECT)
    result = merge([], [ph])
    assert len(result.merged) == 1
    assert result.merged[0].hook == ph
    assert not result.merged[0].is_shadowed


def test_merge_different_types():
    gh = _hook(HookType.STOP, "echo stop")
    ph = _hook(HookType.USER_PROMPT_SUBMIT, "echo submit", level=HookLevel.PROJECT)
    result = merge([gh], [ph])
    assert len(result.merged) == 2
    assert len(result.all_hooks) == 2
    for m in result.merged:
        assert not m.is_shadowed


def test_merge_same_type_same_matcher_shows_shadowing():
    gh = _hook(HookType.PRE_TOOL_USE, "echo global", matcher="Bash")
    ph = _hook(HookType.PRE_TOOL_USE, "echo project", matcher="Bash", level=HookLevel.PROJECT)
    result = merge([gh], [ph])
    assert len(result.merged) == 2

    global_merged = [m for m in result.merged if m.hook.level == HookLevel.GLOBAL]
    project_merged = [m for m in result.merged if m.hook.level == HookLevel.PROJECT]

    assert global_merged[0].shadowed_by == [ph]
    assert project_merged[0].shadowed_by == [gh]


def test_merge_same_type_different_matcher_no_shadowing():
    gh = _hook(HookType.PRE_TOOL_USE, "echo global", matcher="Bash")
    ph = _hook(HookType.PRE_TOOL_USE, "echo project", matcher="Write", level=HookLevel.PROJECT)
    result = merge([gh], [ph])
    for m in result.merged:
        assert not m.is_shadowed


def test_merge_only_global_filter():
    gh = _hook(HookType.STOP, "echo stop")
    ph = _hook(HookType.STOP, "echo stop2", level=HookLevel.PROJECT)
    result = merge([gh], [ph])
    assert len(result.only_global()) == 1
    assert len(result.only_project()) == 1


def test_merge_by_type():
    gh1 = _hook(HookType.STOP, "echo stop")
    gh2 = _hook(HookType.PRE_TOOL_USE, "echo pre")
    ph = _hook(HookType.STOP, "echo stop2", level=HookLevel.PROJECT)
    result = merge([gh1, gh2], [ph])
    stop = result.by_type(HookType.STOP)
    assert len(stop) == 2
    pre = result.by_type(HookType.PRE_TOOL_USE)
    assert len(pre) == 1


def test_merge_empty():
    result = merge([], [])
    assert result.merged == []
    assert result.all_hooks == []
