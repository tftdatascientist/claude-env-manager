from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from razd.tracker.break_engine import RazdBreakEngine, IDLE_RESET_S
from razd.tracker.poller import EventDTO


def _dto(event_type: str = "active", idle: float = 0.0, proc: str = "code.exe") -> EventDTO:
    return EventDTO(
        ts=datetime.datetime.now().isoformat(),
        event_type=event_type,
        process_name=proc,
        window_title="Test",
        url=None,
        idle_seconds=idle,
    )


# --- Akumulacja czasu pracy ---

def test_active_event_accumulates():
    engine = RazdBreakEngine(work_interval_min=50)
    engine.feed(_dto("active"))
    assert engine.worked_seconds == 2.0


def test_multiple_active_events_accumulate():
    engine = RazdBreakEngine(work_interval_min=50)
    for _ in range(5):
        engine.feed(_dto("active"))
    assert engine.worked_seconds == 10.0


def test_idle_below_threshold_does_not_reset():
    engine = RazdBreakEngine(work_interval_min=50)
    engine.feed(_dto("active"))
    engine.feed(_dto("idle", idle=30.0))
    # idle < IDLE_RESET_S — nie resetuje, ale też nie akumuluje
    assert engine.worked_seconds == 2.0


def test_idle_above_threshold_resets():
    engine = RazdBreakEngine(work_interval_min=50)
    for _ in range(10):
        engine.feed(_dto("active"))
    assert engine.worked_seconds == 20.0
    engine.feed(_dto("idle", idle=IDLE_RESET_S + 1))
    assert engine.worked_seconds == 0.0


# --- Sygnał break_due ---

def test_break_due_emitted_at_threshold(qtbot):
    engine = RazdBreakEngine(work_interval_min=1)  # 1 minuta = 60s = 30 pollów
    received = []
    engine.break_due.connect(lambda m: received.append(m))
    for _ in range(30):  # 30 × 2s = 60s
        engine.feed(_dto("active"))
    assert len(received) == 1
    assert received[0] >= 1


def test_break_due_emitted_only_once(qtbot):
    engine = RazdBreakEngine(work_interval_min=1)
    received = []
    engine.break_due.connect(lambda m: received.append(m))
    for _ in range(60):  # 2x próg
        engine.feed(_dto("active"))
    assert len(received) == 1  # nie wielokrotnie


def test_break_due_not_emitted_below_threshold(qtbot):
    engine = RazdBreakEngine(work_interval_min=50)
    received = []
    engine.break_due.connect(lambda m: received.append(m))
    for _ in range(10):
        engine.feed(_dto("active"))
    assert len(received) == 0


# --- take_break ---

def test_take_break_resets_counter():
    engine = RazdBreakEngine(work_interval_min=50)
    for _ in range(10):
        engine.feed(_dto("active"))
    minutes = engine.take_break()
    assert minutes == 0  # 10×2s = 20s < 1 min → 0 całych minut
    assert engine.worked_seconds == 0.0


def test_take_break_returns_minutes_worked():
    engine = RazdBreakEngine(work_interval_min=50)
    for _ in range(90):  # 180s = 3 min
        engine.feed(_dto("active"))
    minutes = engine.take_break()
    assert minutes == 3


def test_take_break_resets_alert_flag(qtbot):
    engine = RazdBreakEngine(work_interval_min=1)
    received = []
    engine.break_due.connect(lambda m: received.append(m))
    for _ in range(30):
        engine.feed(_dto("active"))
    assert len(received) == 1
    engine.take_break()
    # po resecie można znowu osiągnąć próg
    for _ in range(30):
        engine.feed(_dto("active"))
    assert len(received) == 2


# --- Integracja z repo ---

def test_break_engine_with_repo(tmp_path: Path, qtbot):
    from razd.db.repository import RazdRepository
    repo = RazdRepository(tmp_path / "test.db")
    engine = RazdBreakEngine(work_interval_min=1)

    # symuluj: sygnał → zapis do repo
    def on_break(minutes):
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        repo.add_break_event(ts, minutes, "suggested")

    engine.break_due.connect(on_break)
    for _ in range(30):
        engine.feed(_dto("active"))

    events = repo.get_break_events_for_day(datetime.date.today().isoformat())
    assert len(events) == 1
    assert events[0].event_type == "suggested"
    repo.close()
