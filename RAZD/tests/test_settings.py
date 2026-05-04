from __future__ import annotations

from pathlib import Path

import pytest

from razd.config.settings import RazdSettings, _deep_merge, _toml_list


def test_load_defaults() -> None:
    s = RazdSettings.load()
    assert s.tracking.poll_interval_ms == 2000
    assert s.tracking.idle_threshold_secs == 60
    assert s.tracking.browser_url_enabled is True
    assert s.agent.unknown_process_cooldown_secs == 300
    assert s.agent.max_pending_questions == 5
    assert s.focus.default_duration_mins == 25
    assert s.focus.alert_sound is False
    assert s.focus.whitelist == []


def test_db_path_default() -> None:
    s = RazdSettings.load()
    assert s.db_path == Path.home() / ".razd" / "razd.db"


def test_save_and_reload(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("razd.config.settings._USER_CONFIG_PATH", config_path)

    s = RazdSettings.load()
    s.tracking.poll_interval_ms = 4000
    s.focus.whitelist = ["python.exe", "code.exe"]
    s.save_user()

    assert config_path.exists()
    s2 = RazdSettings.load()
    assert s2.tracking.poll_interval_ms == 4000
    assert "python.exe" in s2.focus.whitelist
    assert "code.exe" in s2.focus.whitelist


def test_user_config_overrides_defaults(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[tracking]\nidle_threshold_secs = 120\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("razd.config.settings._USER_CONFIG_PATH", config_path)

    s = RazdSettings.load()
    assert s.tracking.idle_threshold_secs == 120
    assert s.tracking.poll_interval_ms == 2000  # default niezmieniony


def test_deep_merge_nested() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 99}, "c": 4}
    _deep_merge(base, override)
    assert base["a"]["x"] == 1
    assert base["a"]["y"] == 99
    assert base["b"] == 3
    assert base["c"] == 4


def test_toml_list_empty() -> None:
    assert _toml_list([]) == "[]"


def test_toml_list_items() -> None:
    result = _toml_list(["a.exe", "b.exe"])
    assert result == '["a.exe", "b.exe"]'
