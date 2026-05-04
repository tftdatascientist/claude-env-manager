"""Testy scannera 2 poziomów hooków."""

from pathlib import Path
import json
import tempfile

import pytest

from src.hooker.core.model import HookLevel, HookType
from src.hooker.core.scanner import scan_global, scan_project, scan_empty_candidates

FIXTURES = Path(__file__).parent / "fixtures"


def _make_project(tmp_path: Path, settings: dict | None, local: dict | None) -> Path:
    """Pomocnik: tworzy fałszywy projekt z .claude/ w tmp_path."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    if settings is not None:
        (claude / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )
    if local is not None:
        (claude / "settings.local.json").write_text(
            json.dumps(local), encoding="utf-8"
        )
    return tmp_path


def test_scan_global_returns_path():
    hooks, path = scan_global()
    assert path.name == "settings.json"
    assert path.parent.name == ".claude"
    # na maszynie dewelopera global settings istnieje i ma hooki
    assert isinstance(hooks, list)
    for h in hooks:
        assert h.level == HookLevel.GLOBAL


def test_scan_project_single_file(tmp_path):
    settings = {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "echo stop"}]}]}}
    project = _make_project(tmp_path, settings, None)

    hooks, files = scan_project(project)
    assert len(hooks) == 1
    assert hooks[0].hook_type == HookType.STOP
    assert hooks[0].level == HookLevel.PROJECT
    assert any("settings.json" in str(f) for f in files)


def test_scan_project_both_files(tmp_path):
    settings = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]}}
    local = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo submit"}]}]}}
    project = _make_project(tmp_path, settings, local)

    hooks, files = scan_project(project)
    assert len(hooks) == 2
    types = {h.hook_type for h in hooks}
    assert HookType.STOP in types
    assert HookType.USER_PROMPT_SUBMIT in types
    assert len(files) == 2


def test_scan_project_empty_dir(tmp_path):
    (tmp_path / ".claude").mkdir()
    hooks, files = scan_project(tmp_path)
    assert hooks == []
    assert files == []


def test_scan_project_no_claude_dir(tmp_path):
    hooks, files = scan_project(tmp_path)
    assert hooks == []
    assert files == []


def test_scan_empty_candidates_missing_project_files(tmp_path):
    (tmp_path / ".claude").mkdir()
    candidates = scan_empty_candidates(tmp_path)
    names = [p.name for p in candidates]
    assert "settings.json" in names
    assert "settings.local.json" in names


def test_scan_empty_candidates_existing_without_hooks(tmp_path):
    settings = {"permissions": {"allow": []}}
    project = _make_project(tmp_path, settings, None)
    candidates = scan_empty_candidates(project)
    names = [p.name for p in candidates]
    assert "settings.json" in names
