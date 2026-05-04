import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cm.sss_module.core.spawner import ProjectSpawner


@pytest.fixture
def spawner():
    return ProjectSpawner(cc_executable="cc", vscode_executable="code")


def test_spawn_creates_directory(tmp_path, spawner):
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        session_id, project_dir = spawner.spawn("Build a todo app", "my-app", tmp_path)

    assert project_dir.is_dir()
    assert project_dir.name == "my-app"


def test_spawn_writes_intake_json(tmp_path, spawner):
    with patch("subprocess.Popen"):
        session_id, project_dir = spawner.spawn("Build a todo app", "my-app", tmp_path)

    intake = json.loads((project_dir / "intake.json").read_text(encoding="utf-8"))
    assert intake["project_name"] == "my-app"
    assert intake["prompt"] == "Build a todo app"
    assert intake["session_id"] == session_id


def test_spawn_writes_vscode_settings(tmp_path, spawner):
    with patch("subprocess.Popen"):
        _, project_dir = spawner.spawn("prompt", "proj", tmp_path)

    settings = json.loads((project_dir / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    assert settings["claude.plansDirectory"] == "."


def test_spawn_calls_cc_with_plan_flag(tmp_path, spawner):
    with patch("subprocess.Popen") as mock_popen:
        spawner.spawn("my prompt", "proj", tmp_path)

    calls = mock_popen.call_args_list
    cc_call = calls[0][0][0]
    assert "--permission-mode" in cc_call
    assert "plan" in cc_call
    assert "my prompt" in cc_call


def test_spawn_calls_vscode(tmp_path, spawner):
    with patch("subprocess.Popen") as mock_popen:
        _, project_dir = spawner.spawn("p", "proj", tmp_path)

    calls = mock_popen.call_args_list
    code_call = calls[1][0][0]
    assert "code" in code_call
    assert str(project_dir) in code_call


def test_session_id_contains_slug(tmp_path, spawner):
    with patch("subprocess.Popen"):
        session_id, _ = spawner.spawn("p", "my-project", tmp_path)

    assert "my_project" in session_id or "my-project" in session_id


def test_resume_returns_project_dir(tmp_path, spawner):
    existing = tmp_path / "existing-project"
    existing.mkdir()

    with patch("subprocess.Popen") as mock_popen:
        session_id, project_dir = spawner.resume(existing)

    assert project_dir == existing
    assert "existing" in session_id


def test_resume_calls_cc_continue(tmp_path, spawner):
    existing = tmp_path / "proj"
    existing.mkdir()

    with patch("subprocess.Popen") as mock_popen:
        spawner.resume(existing)

    cc_call = mock_popen.call_args_list[0][0][0]
    assert "--continue" in cc_call
    assert "--permission-mode" in cc_call
    assert "plan" in cc_call


def test_resume_raises_if_dir_missing(tmp_path, spawner):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError):
        spawner.resume(missing)
