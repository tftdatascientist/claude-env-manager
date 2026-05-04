from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from razd.tracker.cc_scanner import CcProcessDTO, scan_cc_processes


def _make_proc(pid: int, name: str, cwd: str, cmdline: list[str] | None = None) -> MagicMock:
    p = MagicMock()
    p.info = {"pid": pid, "name": name, "cmdline": cmdline or []}
    p.cwd.return_value = cwd
    return p


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_detects_cc_exe(mock_iter) -> None:
    mock_iter.return_value = [
        _make_proc(1001, "cc.exe", "C:\\projects\\myapp"),
    ]
    result = scan_cc_processes()
    assert len(result) == 1
    dto = next(iter(result))
    assert dto.pid == 1001
    assert dto.exe == "cc.exe"
    assert dto.project_path == "C:\\projects\\myapp"


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_detects_claude_exe(mock_iter) -> None:
    mock_iter.return_value = [
        _make_proc(2002, "claude.exe", "C:\\work\\razd"),
    ]
    result = scan_cc_processes()
    assert any(d.exe == "claude.exe" for d in result)


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_detects_node_with_claude_code(mock_iter) -> None:
    mock_iter.return_value = [
        _make_proc(
            3003, "node.exe", "C:\\projects\\ccnsr",
            cmdline=["node", "C:\\Users\\user\\AppData\\Roaming\\npm\\node_modules\\@anthropic\\claude-code\\cli.js"],
        ),
    ]
    result = scan_cc_processes()
    assert len(result) == 1
    assert next(iter(result)).exe == "node.exe"


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_ignores_unrelated_node(mock_iter) -> None:
    mock_iter.return_value = [
        _make_proc(4004, "node.exe", "C:\\web", cmdline=["node", "server.js"]),
    ]
    result = scan_cc_processes()
    assert len(result) == 0


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_ignores_unrelated_process(mock_iter) -> None:
    mock_iter.return_value = [
        _make_proc(5005, "chrome.exe", "C:\\Users\\user"),
    ]
    result = scan_cc_processes()
    assert len(result) == 0


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_multiple_cc_processes_same_path(mock_iter) -> None:
    """Dwa procesy CC w tym samym CWD → jeden CcProcessDTO na PID."""
    mock_iter.return_value = [
        _make_proc(101, "cc.exe", "C:\\projects\\app"),
        _make_proc(102, "cc.exe", "C:\\projects\\app"),
    ]
    result = scan_cc_processes()
    # frozen dataclass — różne PID → dwa elementy
    assert len(result) == 2


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_access_denied_skipped(mock_iter) -> None:
    import psutil as _psutil
    bad = MagicMock()
    bad.info = {"pid": 999, "name": "cc.exe", "cmdline": []}
    bad.cwd.side_effect = _psutil.AccessDenied(999)
    mock_iter.return_value = [bad]
    result = scan_cc_processes()
    assert len(result) == 0


@patch("razd.tracker.cc_scanner.psutil.process_iter")
def test_no_such_process_skipped(mock_iter) -> None:
    import psutil as _psutil
    bad = MagicMock()
    bad.info = {"pid": 998, "name": "cc.exe", "cmdline": []}
    bad.cwd.side_effect = _psutil.NoSuchProcess(998)
    mock_iter.return_value = [bad]
    result = scan_cc_processes()
    assert len(result) == 0
