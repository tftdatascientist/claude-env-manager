"""Testy loggera — audit log zapisów i restorów."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import src.hooker.core.logger as logger_mod
from src.hooker.core.logger import log_write, log_restore, log_error, read_log


def test_log_write_creates_file(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        log_write(Path("/settings.json"), "abc123", "def456")
        assert log_file.exists()


def test_log_write_valid_json_line(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        log_write(Path("/settings.json"), "abc123", "def456", backup=Path("/settings.20260101.bak"))
        line = log_file.read_text(encoding="utf-8").strip()
        entry = json.loads(line)
        assert entry["action"] == "write"
        assert entry["hash_before"] == "abc123"
        assert entry["hash_after"] == "def456"
        assert entry["backup"] is not None


def test_log_restore(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        log_restore(Path("/settings.json"), Path("/settings.bak"))
        line = log_file.read_text(encoding="utf-8").strip()
        entry = json.loads(line)
        assert entry["action"] == "restore"


def test_log_error(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        log_error(Path("/settings.json"), "Niepoprawna składnia JSON")
        line = log_file.read_text(encoding="utf-8").strip()
        entry = json.loads(line)
        assert entry["action"] == "error"
        assert "JSON" in entry["error"]


def test_read_log_returns_newest_first(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        log_write(Path("/a.json"), "a1", "a2")
        log_write(Path("/b.json"), "b1", "b2")
        log_write(Path("/c.json"), "c1", "c2")
        entries = read_log(10)
        assert entries[0]["file"].endswith("c.json")
        assert entries[1]["file"].endswith("b.json")
        assert entries[2]["file"].endswith("a.json")


def test_read_log_limit(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        for i in range(10):
            log_write(Path(f"/{i}.json"), f"h{i}", f"h{i+1}")
        entries = read_log(3)
        assert len(entries) == 3


def test_read_log_empty(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        entries = read_log()
        assert entries == []


def test_log_utf8_no_bom(tmp_path):
    log_file = tmp_path / "hooker.log"
    with patch.object(logger_mod, "_LOG_PATH", log_file):
        log_write(Path("C:/Users/Sławek/.claude/settings.json"), "a", "b")
        raw = log_file.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert "Sławek".encode("utf-8") in raw
