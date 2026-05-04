"""Testy persistera — atomowy zapis, backup, restore, UTF-8, polskie znaki."""

import json
from pathlib import Path

import pytest

from src.hooker.core.persister import (
    write_settings, restore_from_backup, list_backups, backup_path
)

DATA = {
    "hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "echo Sławek"}]}]
    }
}


def test_write_creates_file(tmp_path):
    target = tmp_path / "settings.json"
    bak, h_before, h_after = write_settings(target, DATA)
    assert target.exists()
    assert bak is None  # brak backupu bo pliku nie było
    assert h_before == ""
    assert h_after


def test_write_valid_json(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo Sławek"


def test_write_utf8_no_bom(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    raw = target.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "Plik nie powinien mieć BOM"
    assert b"S\xc5\x82awek" in raw  # UTF-8 dla 'Sławek'


def test_write_creates_backup_on_overwrite(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    bak, h_before, h_after = write_settings(target, {"hooks": {}})
    assert bak is not None
    assert bak.exists()
    assert bak.suffix == ".bak"
    assert h_before  # hash poprzedniego pliku


def test_write_backup_contains_old_data(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    write_settings(target, {"hooks": {}})
    baks = list_backups(target)
    assert len(baks) == 1
    old = json.loads(baks[0].read_bytes().decode("utf-8"))
    assert "Stop" in old["hooks"]


def test_list_backups_sorted_newest_first(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    write_settings(target, {"hooks": {"Stop": []}})
    write_settings(target, {"hooks": {}})
    baks = list_backups(target)
    assert len(baks) == 2
    assert baks[0].stat().st_mtime >= baks[1].stat().st_mtime


def test_restore_from_backup(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    _, _, _ = write_settings(target, {"hooks": {}})
    baks = list_backups(target)
    restore_from_backup(baks[0], target)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert "Stop" in loaded["hooks"]


def test_restore_nonexistent_backup(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    with pytest.raises(FileNotFoundError):
        restore_from_backup(tmp_path / "nonexistent.20991231_235959.bak", target)


def test_write_polish_path(tmp_path):
    """Edge case: ścieżka z polskimi znakami."""
    polish_dir = tmp_path / "Sławek" / ".claude"
    polish_dir.mkdir(parents=True)
    target = polish_dir / "settings.json"
    bak, _, _ = write_settings(target, DATA)
    assert target.exists()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert "Stop" in loaded["hooks"]


def test_write_lf_line_endings(tmp_path):
    target = tmp_path / "settings.json"
    write_settings(target, DATA)
    raw = target.read_bytes()
    assert b"\r\n" not in raw, "Plik nie powinien mieć CRLF"
