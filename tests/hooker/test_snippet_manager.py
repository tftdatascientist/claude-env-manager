"""Testy snippet_manager — load_snippets, snippets_for_type, Snippet.from_dict."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.hooker.core.snippet_manager import Snippet, load_snippets, snippets_for_type


def test_snippet_from_dict_full():
    d = {
        "name": "Test hook",
        "hook_type": "PreToolUse",
        "command": "python hook.py",
        "description": "Opis testowy",
        "matcher": "Bash",
        "tags": ["safety", "bash"],
    }
    s = Snippet.from_dict(d)
    assert s.name == "Test hook"
    assert s.hook_type == "PreToolUse"
    assert s.command == "python hook.py"
    assert s.description == "Opis testowy"
    assert s.matcher == "Bash"
    assert s.tags == ["safety", "bash"]


def test_snippet_from_dict_defaults():
    s = Snippet.from_dict({"name": "x", "hook_type": "Stop", "command": "cmd"})
    assert s.description == ""
    assert s.matcher == ""
    assert s.tags == []


def test_load_snippets_returns_list():
    snippets = load_snippets()
    assert isinstance(snippets, list)


def test_load_snippets_builtin_nonempty():
    snippets = load_snippets()
    assert len(snippets) >= 10


def test_load_snippets_all_have_name_and_command():
    for s in load_snippets():
        assert s.name, f"Snippet bez nazwy: {s}"
        assert s.command, f"Snippet bez command: {s.name}"


def test_load_snippets_valid_hook_types():
    valid = {
        "PreToolUse", "PostToolUse", "Stop", "Notification",
        "UserPromptSubmit", "SessionEnd", "SessionStart",
        "SubagentStop", "PreCompact",
    }
    for s in load_snippets():
        assert s.hook_type in valid, f"Nieznany hook_type: {s.hook_type} w '{s.name}'"


def test_snippets_for_type_filters():
    pre = snippets_for_type("PreToolUse")
    assert all(s.hook_type == "PreToolUse" for s in pre)


def test_snippets_for_type_unknown_returns_empty():
    result = snippets_for_type("NieIstniejacyTyp")
    assert result == []


def test_snippets_for_type_stop_has_entries():
    stops = snippets_for_type("Stop")
    assert len(stops) >= 1


def test_load_snippets_user_override(tmp_path: Path, monkeypatch):
    user_yaml = tmp_path / "hooker_snippets_user.yaml"
    user_yaml.write_text(
        "snippets:\n"
        "  - name: \"Blokuj rm -rf\"\n"
        "    hook_type: PreToolUse\n"
        "    matcher: Bash\n"
        "    command: python override.py\n"
        "    description: Override builtin\n"
        "    tags: [override]\n",
        encoding="utf-8",
    )
    import src.hooker.core.snippet_manager as sm
    monkeypatch.setattr(sm, "_USER_PATH", user_yaml)
    snippets = load_snippets()
    overridden = next((s for s in snippets if s.name == "Blokuj rm -rf"), None)
    assert overridden is not None
    assert overridden.command == "python override.py"
