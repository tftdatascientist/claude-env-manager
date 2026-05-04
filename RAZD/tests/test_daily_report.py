from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from razd.db.repository import RazdRepository


@pytest.fixture
def repo(tmp_path: Path) -> RazdRepository:
    r = RazdRepository(tmp_path / "test.db")
    yield r
    r.close()


def _today() -> str:
    return datetime.date.today().isoformat()


# --- get_daily_report ---

def test_empty_day_report(repo: RazdRepository):
    report = repo.get_daily_report(_today())
    assert report.total_active_s == 0
    assert report.productive_s == 0
    assert report.idle_s == 0
    assert report.productivity_score == 0
    assert report.top_categories == []
    assert report.focus_sessions == []
    assert report.cc_sessions == []
    assert report.break_events == []
    assert report.distraction_events == []


def test_report_counts_active_time(repo: RazdRepository):
    today = _today()
    cid = repo.upsert_category("Praca", "#00ff00", is_productive=True)
    raw = json.dumps({"event_type": "active"})
    repo.insert_event(f"{today}T10:00:00", "active", raw, process_name="code.exe", category_id=cid)
    repo.insert_event(f"{today}T10:00:02", "active", raw, process_name="code.exe", category_id=cid)
    repo.insert_event(f"{today}T10:00:04", "active", raw, process_name="code.exe", category_id=cid)
    report = repo.get_daily_report(today)
    assert report.total_active_s > 0


def test_report_counts_idle_time(repo: RazdRepository):
    today = _today()
    raw = json.dumps({"event_type": "idle"})
    repo.insert_event(f"{today}T10:00:00", "idle", raw, idle_seconds=120)
    repo.insert_event(f"{today}T10:02:00", "idle", raw, idle_seconds=120)
    report = repo.get_daily_report(today)
    assert report.idle_s > 0


def test_report_productivity_score(repo: RazdRepository):
    today = _today()
    cid_prod = repo.upsert_category("Praca", "#00ff00", is_productive=True)
    cid_dist = repo.upsert_category("Rozrywka", "#ff0000", is_productive=False)
    raw = json.dumps({"event_type": "active"})
    # 3 produktywne
    for i in range(3):
        repo.insert_event(
            f"{today}T10:00:{i*2:02d}", "active", raw,
            process_name="code.exe", category_id=cid_prod,
        )
    # 1 nieproduktywny
    repo.insert_event(f"{today}T10:00:06", "active", raw, process_name="youtube.exe", category_id=cid_dist)
    report = repo.get_daily_report(today)
    assert 0 <= report.productivity_score <= 100


def test_report_top_categories(repo: RazdRepository):
    today = _today()
    cid = repo.upsert_category("IDE", "#0000ff", is_productive=True)
    raw = json.dumps({"event_type": "active"})
    for i in range(5):
        repo.insert_event(
            f"{today}T09:00:{i*2:02d}", "active", raw,
            process_name="code.exe", category_id=cid,
        )
    report = repo.get_daily_report(today)
    assert len(report.top_categories) > 0
    assert report.top_categories[0][0] == "IDE"


def test_report_includes_focus_sessions(repo: RazdRepository):
    today = _today()
    sid = repo.start_focus_session(f"{today}T11:00:00", {"code.exe"})
    repo.end_focus_session(sid, f"{today}T11:25:00", 1500, 9)
    report = repo.get_daily_report(today)
    assert len(report.focus_sessions) == 1
    assert report.focus_sessions[0].score == 9


def test_report_includes_cc_sessions(repo: RazdRepository):
    today = _today()
    sid = repo.open_cc_session("C:\\projects\\razd", f"{today}T09:00:00")
    repo.close_cc_session(sid, f"{today}T09:30:00", 1800)
    report = repo.get_daily_report(today)
    assert len(report.cc_sessions) == 1
    assert "razd" in report.cc_sessions[0].project_path


def test_report_includes_break_events(repo: RazdRepository):
    today = _today()
    repo.add_break_event(f"{today}T12:00:00", 50, "suggested")
    repo.add_break_event(f"{today}T12:05:00", 50, "taken")
    report = repo.get_daily_report(today)
    assert len(report.break_events) == 2
    types = {b.event_type for b in report.break_events}
    assert "suggested" in types and "taken" in types


def test_report_includes_distraction_events(repo: RazdRepository):
    today = _today()
    repo.add_distraction_event(f"{today}T14:00:00", 8.5, 60)
    report = repo.get_daily_report(today)
    assert len(report.distraction_events) == 1
    assert report.distraction_events[0].switches_per_min == 8.5


def test_report_wrong_day_empty(repo: RazdRepository):
    today = _today()
    cid = repo.upsert_category("Praca", "#fff", is_productive=True)
    raw = json.dumps({"event_type": "active"})
    repo.insert_event(f"{today}T10:00:00", "active", raw, process_name="code.exe", category_id=cid)
    report = repo.get_daily_report("2000-01-01")
    assert report.total_active_s == 0


# --- Smoke test dialogu ---

def test_report_dialog_smoke(qtbot, tmp_path: Path):
    from razd.ui.report_dialog import RazdDailyReportDialog
    repo = RazdRepository(tmp_path / "test.db")
    report = repo.get_daily_report(_today())
    dlg = RazdDailyReportDialog(report)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.isVisible()
    repo.close()


def test_report_dialog_with_data(qtbot, tmp_path: Path):
    from razd.ui.report_dialog import RazdDailyReportDialog
    repo = RazdRepository(tmp_path / "test.db")
    today = _today()
    cid = repo.upsert_category("Praca", "#0f0", is_productive=True)
    raw = json.dumps({"event_type": "active"})
    for i in range(10):
        repo.insert_event(f"{today}T10:00:{i*2:02d}", "active", raw, process_name="code.exe", category_id=cid)
    sid = repo.start_focus_session(f"{today}T11:00:00", {"code.exe"})
    repo.end_focus_session(sid, f"{today}T11:25:00", 1500, 8)
    repo.add_break_event(f"{today}T12:00:00", 50, "suggested")
    repo.add_distraction_event(f"{today}T14:00:00", 7.2, 60)
    report = repo.get_daily_report(today)
    dlg = RazdDailyReportDialog(report)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.isVisible()
    repo.close()
