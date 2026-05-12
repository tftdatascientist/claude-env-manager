from __future__ import annotations

import pytest
from pathlib import Path
from razd.db.repository import RazdRepository, DayStats


@pytest.fixture
def repo(tmp_path):
    r = RazdRepository(tmp_path / "test.db")
    yield r
    r.close()


def _ts(date: str, h: int, m: int, s: int = 0) -> str:
    return f"{date}T{h:02d}:{m:02d}:{s:02d}"


def test_empty_day(repo):
    stats = repo.compute_day_stats("2024-01-01")
    assert stats.uptime_s == 0
    assert stats.active_s == 0
    assert stats.idle_s == 0


def test_single_active_event(repo):
    date = "2024-01-15"
    repo.insert_event(_ts(date, 10, 0, 0), "active", "{}", process_name="code.exe")
    stats = repo.compute_day_stats(date)
    assert stats.uptime_s >= 2
    assert stats.active_s >= 2
    assert stats.idle_s == 0


def test_active_and_idle(repo):
    date = "2024-01-15"
    raw = "{}"
    for s in [0, 2, 4]:
        repo.insert_event(_ts(date, 10, 0, s), "active", raw, process_name="code.exe")
    for s in [6, 8]:
        repo.insert_event(_ts(date, 10, 0, s), "idle", raw, idle_seconds=120)
    stats = repo.compute_day_stats(date)
    assert stats.active_s > 0
    assert stats.idle_s > 0
    assert stats.uptime_s >= stats.active_s + stats.idle_s - 10


def test_uptime_spans_full_session(repo):
    date = "2024-01-15"
    raw = "{}"
    repo.insert_event(_ts(date, 9, 0, 0), "active", raw)
    repo.insert_event(_ts(date, 17, 0, 0), "active", raw)
    stats = repo.compute_day_stats(date)
    assert stats.uptime_s >= 8 * 3600


def test_overlapping_not_negative(repo):
    date = "2024-01-15"
    raw = "{}"
    for _ in range(3):
        repo.insert_event(_ts(date, 10, 0, 0), "active", raw)
    stats = repo.compute_day_stats(date)
    assert stats.active_s >= 0
    assert stats.idle_s >= 0


def test_partial_day_no_crash(repo):
    date = "2024-01-15"
    repo.insert_event(_ts(date, 23, 59, 58), "active", "{}")
    stats = repo.compute_day_stats(date)
    assert stats.uptime_s >= 0


def test_returns_day_stats_type(repo):
    stats = repo.compute_day_stats("2024-03-01")
    assert isinstance(stats, DayStats)
    assert stats.date == "2024-03-01"
