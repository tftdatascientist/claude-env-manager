from __future__ import annotations

import json
from pathlib import Path

import pytest

from razd.db.repository import RazdRepository


@pytest.fixture
def repo(tmp_path: Path) -> RazdRepository:
    r = RazdRepository(tmp_path / "test.db")
    yield r
    r.close()


def test_upsert_and_get_category(repo: RazdRepository) -> None:
    cid = repo.upsert_category("Praca", "#00ff00", is_productive=True)
    cat = repo.get_category_by_name("Praca")
    assert cat is not None
    assert cat.id == cid
    assert cat.color == "#00ff00"
    assert cat.is_productive is True


def test_upsert_category_idempotent(repo: RazdRepository) -> None:
    id1 = repo.upsert_category("Dev", "#ff0000")
    id2 = repo.upsert_category("Dev", "#0000ff")
    assert id1 == id2
    cat = repo.get_category_by_name("Dev")
    assert cat is not None
    assert cat.color == "#0000ff"


def test_process_category(repo: RazdRepository) -> None:
    cid = repo.upsert_category("IDE", "#aabbcc")
    repo.upsert_process("code.exe", cid)
    assert repo.get_category_for_process("code.exe") == cid
    assert repo.get_category_for_process("unknown.exe") is None


def test_url_mapping(repo: RazdRepository) -> None:
    cid = repo.upsert_category("Social", "#ff00ff")
    repo.upsert_url_mapping("twitter.com", cid)
    assert repo.get_category_for_url("https://twitter.com/home") == cid
    assert repo.get_category_for_url("https://github.com") is None


def test_insert_and_get_event(repo: RazdRepository) -> None:
    raw = json.dumps({"ts": "2026-04-29T10:00:00", "event_type": "active"})
    eid = repo.insert_event(
        ts="2026-04-29T10:00:00",
        event_type="active",
        raw_json=raw,
        process_name="code.exe",
        window_title="main.py — RAZD",
    )
    events = repo.get_events_for_day("2026-04-29")
    assert len(events) == 1
    assert events[0].id == eid
    assert events[0].process_name == "code.exe"


def test_save_decision(repo: RazdRepository) -> None:
    did = repo.save_decision(
        subject="notepad.exe",
        subject_type="process",
        question="Co to za proces?",
        answer="Notatnik systemowy",
    )
    assert did > 0


# --- Focus sessions ---

def test_start_focus_session(repo: RazdRepository) -> None:
    sid = repo.start_focus_session("2026-05-02T10:00:00", {"python.exe", "code.exe"})
    assert sid > 0
    sessions = repo.get_focus_sessions_for_day("2026-05-02")
    assert len(sessions) == 1
    assert sessions[0].id == sid
    assert sessions[0].ended_at is None
    assert sessions[0].score is None


def test_end_focus_session(repo: RazdRepository) -> None:
    sid = repo.start_focus_session("2026-05-02T10:00:00", {"python.exe"})
    repo.end_focus_session(sid, "2026-05-02T10:30:00", 1800, 8)
    sessions = repo.get_focus_sessions_for_day("2026-05-02")
    assert sessions[0].ended_at == "2026-05-02T10:30:00"
    assert sessions[0].duration_s == 1800
    assert sessions[0].score == 8


def test_focus_process_samples(repo: RazdRepository) -> None:
    sid = repo.start_focus_session("2026-05-02T10:00:00", set())
    repo.add_focus_process_sample(sid, "2026-05-02T10:00:02", "python.exe")
    repo.add_focus_process_sample(sid, "2026-05-02T10:00:04", "chrome.exe")
    samples = repo.get_focus_process_samples(sid)
    assert len(samples) == 2
    assert samples[0] == ("2026-05-02T10:00:02", "python.exe")
    assert samples[1] == ("2026-05-02T10:00:04", "chrome.exe")


def test_focus_sessions_day_filter(repo: RazdRepository) -> None:
    repo.start_focus_session("2026-05-01T09:00:00", set())
    repo.start_focus_session("2026-05-02T11:00:00", set())
    assert len(repo.get_focus_sessions_for_day("2026-05-01")) == 1
    assert len(repo.get_focus_sessions_for_day("2026-05-02")) == 1


def test_whitelist_snapshot_stored_as_json(repo: RazdRepository) -> None:
    sid = repo.start_focus_session("2026-05-02T10:00:00", {"a.exe", "b.exe"})
    sessions = repo.get_focus_sessions_for_day("2026-05-02")
    loaded = json.loads(sessions[0].whitelist_snapshot)
    assert set(loaded) == {"a.exe", "b.exe"}


# --- CC sessions ---

def test_open_cc_session(repo: RazdRepository) -> None:
    sid = repo.open_cc_session("C:\\projects\\razd", "2026-05-02T09:00:00")
    assert sid > 0
    sessions = repo.get_cc_sessions_for_day("2026-05-02")
    assert len(sessions) == 1
    assert sessions[0].project_path == "C:\\projects\\razd"
    assert sessions[0].ended_at is None


def test_close_cc_session(repo: RazdRepository) -> None:
    sid = repo.open_cc_session("C:\\projects\\razd", "2026-05-02T09:00:00")
    repo.close_cc_session(sid, "2026-05-02T09:30:00", 1800)
    sessions = repo.get_cc_sessions_for_day("2026-05-02")
    assert sessions[0].ended_at == "2026-05-02T09:30:00"
    assert sessions[0].duration_s == 1800


def test_add_cc_snapshot(repo: RazdRepository) -> None:
    sid = repo.open_cc_session("C:\\projects\\razd", "2026-05-02T09:00:00")
    repo.add_cc_snapshot(sid, "2026-05-02T09:00:02", 1234, "cc.exe")
    repo.add_cc_snapshot(sid, "2026-05-02T09:00:04", 1234, "cc.exe")
    # snapshot nie ma własnego get — weryfikujemy przez brak wyjątku i zamknięcie sesji
    repo.close_cc_session(sid, "2026-05-02T09:00:10", 8)
    sessions = repo.get_cc_sessions_for_day("2026-05-02")
    assert sessions[0].duration_s == 8


def test_cc_sessions_day_filter(repo: RazdRepository) -> None:
    repo.open_cc_session("C:\\p\\a", "2026-05-01T10:00:00")
    repo.open_cc_session("C:\\p\\b", "2026-05-02T11:00:00")
    assert len(repo.get_cc_sessions_for_day("2026-05-01")) == 1
    assert len(repo.get_cc_sessions_for_day("2026-05-02")) == 1
