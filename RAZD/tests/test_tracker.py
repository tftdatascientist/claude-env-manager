from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from razd.tracker.browser_url import sanitize_url
from razd.tracker.idle import get_idle_seconds
from razd.tracker.active_window import WindowInfo


# --- sanitize_url ---

def test_sanitize_url_removes_token() -> None:
    url = "https://example.com/api?token=abc123&foo=bar"
    result = sanitize_url(url)
    assert "abc123" not in result
    assert "foo=bar" in result


def test_sanitize_url_removes_multiple_secrets() -> None:
    url = "https://x.com/?access_token=XYZ&api_key=SECRET&page=1"
    result = sanitize_url(url)
    assert "XYZ" not in result
    assert "SECRET" not in result
    assert "page=1" in result


def test_sanitize_url_clean_passthrough() -> None:
    url = "https://github.com/user/repo"
    assert sanitize_url(url) == url


# --- idle ---

def test_get_idle_seconds_returns_float() -> None:
    with (
        patch("ctypes.windll.user32.GetLastInputInfo", return_value=None),
        patch("ctypes.windll.kernel32.GetTickCount", return_value=5000),
    ):
        result = get_idle_seconds()
        assert isinstance(result, float)
        assert result >= 0


# --- active_window mock ---

def test_get_active_window_returns_window_info() -> None:
    mock_proc = MagicMock()
    mock_proc.name.return_value = "code.exe"

    with (
        patch("razd.tracker.active_window.win32gui.GetForegroundWindow", return_value=1234),
        patch("razd.tracker.active_window.win32gui.GetWindowText", return_value="main.py — VS Code"),
        patch("razd.tracker.active_window.win32process.GetWindowThreadProcessId", return_value=(0, 999)),
        patch("razd.tracker.active_window.psutil.Process", return_value=mock_proc),
    ):
        from razd.tracker.active_window import get_active_window
        info = get_active_window()

    assert info is not None
    assert info.process_name == "code.exe"
    assert info.window_title == "main.py — VS Code"
    assert info.pid == 999


def test_get_active_window_no_hwnd() -> None:
    with patch("razd.tracker.active_window.win32gui.GetForegroundWindow", return_value=0):
        from razd.tracker.active_window import get_active_window
        assert get_active_window() is None


# --- EventDTO ---

def test_event_dto_to_json() -> None:
    from razd.tracker.poller import EventDTO
    import json

    dto = EventDTO(
        ts="2026-04-29T10:00:00+00:00",
        event_type="active",
        process_name="code.exe",
        window_title="test",
        url=None,
        idle_seconds=0.0,
    )
    data = json.loads(dto.to_json())
    assert data["event_type"] == "active"
    assert data["process_name"] == "code.exe"
    assert data["url"] is None
