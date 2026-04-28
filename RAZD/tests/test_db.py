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
