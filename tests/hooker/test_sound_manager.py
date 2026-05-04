"""Testy sound_manager — load/save config, build_sound_hooks, hook_command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.hooker.core.sound_manager as sm
from src.hooker.core.sound_manager import (
    SOUND_EVENT_TYPES,
    build_sound_hooks,
    hook_command,
    load_config,
    save_config,
    install_hook_script,
)


@pytest.fixture(autouse=True)
def patch_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sm, "_CONFIG_PATH", tmp_path / "sound_config.json")
    monkeypatch.setattr(sm, "_HOOK_SCRIPT_PATH", tmp_path / "sound_hook.py")


# ------------------------------------------------------------------ load_config

def test_load_config_missing_returns_defaults():
    cfg = load_config()
    assert cfg == {"sounds": {}, "enabled": []}


def test_load_config_malformed_returns_defaults(tmp_path: Path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{INVALID}", encoding="utf-8")
    monkeypatch.setattr(sm, "_CONFIG_PATH", bad)
    assert load_config() == {"sounds": {}, "enabled": []}


def test_load_config_reads_saved():
    cfg = {"sounds": {"Stop": "/path/to/stop.wav"}, "enabled": ["Stop"]}
    save_config(cfg)
    loaded = load_config()
    assert loaded["sounds"]["Stop"] == "/path/to/stop.wav"
    assert "Stop" in loaded["enabled"]


# ------------------------------------------------------------------ save_config

def test_save_config_creates_file():
    cfg = {"sounds": {}, "enabled": []}
    save_config(cfg)
    assert sm._CONFIG_PATH.exists()


def test_save_config_utf8_polish_chars(tmp_path: Path):
    cfg = {"sounds": {"Stop": "C:/Użytkownicy/plik.wav"}, "enabled": []}
    save_config(cfg)
    text = sm._CONFIG_PATH.read_text(encoding="utf-8")
    assert "Użytkownicy" in text


def test_save_config_valid_json():
    cfg = {"sounds": {"Notification": "/a.wav"}, "enabled": ["Notification"]}
    save_config(cfg)
    data = json.loads(sm._CONFIG_PATH.read_text(encoding="utf-8"))
    assert data["enabled"] == ["Notification"]


# ------------------------------------------------------------------ hook_command

def test_hook_command_contains_event_type():
    cmd = hook_command("Stop")
    assert "Stop" in cmd


def test_hook_command_uses_forward_slashes():
    cmd = hook_command("Notification")
    assert "\\" not in cmd


# ------------------------------------------------------------------ build_sound_hooks

def test_build_sound_hooks_empty_config():
    hooks = build_sound_hooks({"sounds": {}, "enabled": []})
    assert hooks == {}


def test_build_sound_hooks_enabled_event():
    cfg = {"sounds": {"Stop": "/s.wav"}, "enabled": ["Stop"]}
    hooks = build_sound_hooks(cfg)
    assert "Stop" in hooks
    assert len(hooks["Stop"]) == 1


def test_build_sound_hooks_disabled_not_included():
    cfg = {"sounds": {"Stop": "/s.wav", "Notification": "/n.wav"}, "enabled": ["Stop"]}
    hooks = build_sound_hooks(cfg)
    assert "Stop" in hooks
    assert "Notification" not in hooks


def test_build_sound_hooks_missing_sound_skipped():
    cfg = {"sounds": {}, "enabled": ["Stop"]}
    hooks = build_sound_hooks(cfg)
    assert "Stop" not in hooks


# ------------------------------------------------------------------ install_hook_script

def test_install_hook_script_creates_file():
    path = install_hook_script()
    assert path.exists()


def test_install_hook_script_is_python():
    path = install_hook_script()
    content = path.read_text(encoding="utf-8")
    assert "#!/usr/bin/env python3" in content
    assert "def main" in content


# ------------------------------------------------------------------ SOUND_EVENT_TYPES

def test_sound_event_types_has_core_events():
    for evt in ("Stop", "Notification", "SessionEnd", "SessionStart"):
        assert evt in SOUND_EVENT_TYPES
