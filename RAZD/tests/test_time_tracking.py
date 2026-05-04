from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from razd.db.repository import RazdRepository
from razd.ui.time_tracking_tab import RazdTimeTrackingTab, _color_for, _CATEGORY_COLORS
from razd.tracker.poller import EventDTO


@pytest.fixture
def repo(tmp_path: Path) -> RazdRepository:
    r = RazdRepository(tmp_path / "test.db")
    yield r
    r.close()


def _make_dto(
    process: str = "code.exe",
    event_type: str = "active",
    url: str | None = None,
    idle: float = 0.0,
) -> EventDTO:
    return EventDTO(
        ts=datetime.datetime.now().isoformat(),
        event_type=event_type,
        process_name=process,
        window_title="Test Window",
        url=url,
        idle_seconds=idle,
    )


# --- _color_for ---

def test_color_for_consistent() -> None:
    c1 = _color_for("Praca")
    c2 = _color_for("Praca")
    assert c1 == c2
    assert c1.startswith("#")


def test_color_for_unique_per_category() -> None:
    _color_for("Cat_A")
    _color_for("Cat_B")
    assert _color_for("Cat_A") != _color_for("Cat_B")


# --- RazdTimeTrackingTab ---

def test_tab_shows_process_name(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab.on_event(_make_dto("python.exe"))
    assert "python.exe" in tab._status.text()


def test_tab_shows_idle(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab.on_event(_make_dto(event_type="idle", idle=120.0))
    assert "Przerwa" in tab._status.text()
    assert "120" in tab._status.text()


def test_tab_shows_url(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab.on_event(_make_dto(url="https://github.com"))
    assert "github.com" in tab._status.text()


def test_accumulates_seconds(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    dto = _make_dto("code.exe")
    tab.on_event(dto)
    import time
    time.sleep(0.05)
    tab.on_event(dto)
    # po dwóch eventach w krótkim czasie, coś powinno być w session_seconds lub last_ts ustawiony
    assert tab._last_category is not None


def test_load_day_from_db(qtbot, repo) -> None:
    cid = repo.upsert_category("Dev", "#00aaff")
    import json
    today = datetime.date.today().isoformat()
    repo.insert_event(
        ts=f"{today}T09:00:00",
        event_type="active",
        raw_json=json.dumps({"event_type": "active"}),
        process_name="code.exe",
        category_id=cid,
    )
    repo.insert_event(
        ts=f"{today}T09:00:02",
        event_type="active",
        raw_json=json.dumps({"event_type": "active"}),
        process_name="code.exe",
        category_id=cid,
    )

    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab._load_day_from_db(today)

    assert len(tab._segments) > 0
    assert "Dev" in tab._session_seconds
    assert tab._session_seconds["Dev"] > 0


def test_resolve_category_fallback(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    dto = _make_dto("mspaint.exe")
    cat = tab._resolve_category(dto)
    assert cat == "mspaint.exe"  # fallback do nazwy procesu


def test_resolve_category_from_process(qtbot, repo) -> None:
    cid = repo.upsert_category("IDE", "#ffffff")
    repo.upsert_process("code.exe", cid)
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    dto = _make_dto("code.exe")
    cat = tab._resolve_category(dto)
    assert cat == "IDE"


def test_resolve_category_from_url(qtbot, repo) -> None:
    cid = repo.upsert_category("Social", "#ff00ff")
    repo.upsert_url_mapping("twitter.com", cid)
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    dto = _make_dto(url="https://twitter.com/home")
    cat = tab._resolve_category(dto)
    assert cat == "Social"


# --- Focus bloki na osi czasu ---

def test_on_focus_session_adds_block(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    today = datetime.date.today().isoformat()
    tab.on_focus_session(f"{today}T10:00:00", f"{today}T10:30:00", 1800, 7)
    assert len(tab._focus_blocks) == 1
    start_h, end_h, score = tab._focus_blocks[0]
    assert abs(start_h - 10.0) < 0.01
    assert abs(end_h - 10.5) < 0.01
    assert score == 7


def test_on_focus_session_updates_timeline(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    today = datetime.date.today().isoformat()
    tab.on_focus_session(f"{today}T09:00:00", f"{today}T09:25:00", 1500, 10)
    assert tab._timeline._focus_blocks == tab._focus_blocks


def test_load_day_from_db_includes_focus(qtbot, repo) -> None:
    today = datetime.date.today().isoformat()
    sid = repo.start_focus_session(f"{today}T14:00:00", {"code.exe"})
    repo.end_focus_session(sid, f"{today}T14:30:00", 1800, 9)

    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab._load_day_from_db(today)

    assert len(tab._focus_blocks) == 1
    _, _, score = tab._focus_blocks[0]
    assert score == 9


def test_go_today_clears_focus_blocks(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    today = datetime.date.today().isoformat()
    tab.on_focus_session(f"{today}T10:00:00", f"{today}T10:30:00", 1800, 5)
    assert len(tab._focus_blocks) == 1
    tab._go_today()
    assert len(tab._focus_blocks) == 0


# --- CC bloki na osi czasu ---

def test_on_cc_session_started_adds_to_active(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab.on_cc_session_started("C:\\projects\\myapp", 1)
    assert "C:\\projects\\myapp" in tab._active_cc
    assert tab._cc_list.count() == 1


def test_on_cc_session_ended_adds_block(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    import time
    tab.on_cc_session_started("C:\\projects\\myapp", 1)
    time.sleep(0.01)
    tab.on_cc_session_ended("C:\\projects\\myapp", 10)
    assert len(tab._cc_blocks) == 1
    _, _, proj = tab._cc_blocks[0]
    assert proj == "myapp"
    assert "C:\\projects\\myapp" not in tab._active_cc
    assert tab._cc_list.count() == 0


def test_load_day_from_db_includes_cc(qtbot, repo) -> None:
    today = datetime.date.today().isoformat()
    sid = repo.open_cc_session("C:\\projects\\razd", f"{today}T11:00:00")
    repo.close_cc_session(sid, f"{today}T11:45:00", 2700)

    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab._load_day_from_db(today)

    assert len(tab._cc_blocks) == 1
    _, _, proj = tab._cc_blocks[0]
    assert proj == "razd"


def test_go_today_clears_cc_blocks(qtbot, repo) -> None:
    tab = RazdTimeTrackingTab(repo=repo)
    qtbot.addWidget(tab)
    tab.on_cc_session_started("C:\\projects\\x", 1)
    tab.on_cc_session_ended("C:\\projects\\x", 60)
    assert len(tab._cc_blocks) == 1
    tab._go_today()
    assert len(tab._cc_blocks) == 0
