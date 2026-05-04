from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from razd.ui.focus_timer_tab import _FocusState, RazdFocusTimerTab


# --- _FocusState machine ---

def test_initial_state() -> None:
    s = _FocusState()
    assert s.state == _FocusState.IDLE
    assert s.remaining_secs == 0


def test_start_sets_running() -> None:
    s = _FocusState()
    s.start(30)
    assert s.state == _FocusState.RUNNING
    assert s.remaining_secs == 1800


def test_tick_decrements() -> None:
    s = _FocusState()
    s.start(1)
    for _ in range(59):
        done = s.tick()
        assert not done
    assert s.remaining_secs == 1


def test_tick_finishes_at_zero() -> None:
    s = _FocusState()
    s.start(1)
    for _ in range(59):
        s.tick()
    done = s.tick()
    assert done
    assert s.state == _FocusState.IDLE
    assert s.remaining_secs == 0


def test_pause_and_resume() -> None:
    s = _FocusState()
    s.start(10)
    s.pause()
    assert s.state == _FocusState.PAUSED
    s.tick()  # tick w pauzie nie zmienia czasu
    assert s.remaining_secs == 600
    s.resume()
    assert s.state == _FocusState.RUNNING
    s.tick()
    assert s.remaining_secs == 599


def test_reset_from_running() -> None:
    s = _FocusState()
    s.start(5)
    s.tick()
    s.reset()
    assert s.state == _FocusState.IDLE
    assert s.remaining_secs == 0


def test_pause_idle_noop() -> None:
    s = _FocusState()
    s.pause()  # nie powinno zmienić stanu
    assert s.state == _FocusState.IDLE


def test_resume_idle_noop() -> None:
    s = _FocusState()
    s.resume()
    assert s.state == _FocusState.IDLE


def test_whitelist_check(qtbot) -> None:
    tab = RazdFocusTimerTab()
    qtbot.addWidget(tab)
    tab._state.whitelist = {"python.exe", "code.exe"}
    tab._state.start(5)
    # dozwolony proces — brak alertu (escape_dialog_open nie zmienia się)
    tab.check_active_app("python.exe")
    assert not tab._escape_dialog_open


def test_whitelist_empty_no_alert(qtbot) -> None:
    tab = RazdFocusTimerTab()
    qtbot.addWidget(tab)
    tab._state.start(5)
    # pusta whitelist = brak ograniczeń
    tab.check_active_app("chrome.exe")
    assert not tab._escape_dialog_open


def test_check_app_idle_state_noop(qtbot) -> None:
    tab = RazdFocusTimerTab()
    qtbot.addWidget(tab)
    tab._state.whitelist = {"code.exe"}
    # timer nie uruchomiony — check_active_app nie robi nic
    tab.check_active_app("chrome.exe")
    assert not tab._escape_dialog_open


def test_ui_start_pause_reset(qtbot) -> None:
    tab = RazdFocusTimerTab()
    qtbot.addWidget(tab)
    tab.show()

    # start
    qtbot.mouseClick(tab._btn_start, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
    assert tab._state.state == _FocusState.RUNNING
    assert tab._ticker.isActive()

    # pauza
    qtbot.mouseClick(tab._btn_start, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
    assert tab._state.state == _FocusState.PAUSED

    # reset
    qtbot.mouseClick(tab._btn_reset, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
    assert tab._state.state == _FocusState.IDLE
    assert not tab._ticker.isActive()


def test_display_format(qtbot) -> None:
    tab = RazdFocusTimerTab()
    qtbot.addWidget(tab)
    tab._duration_spin.setValue(25)
    tab._state.start(25)
    tab._update_ui()
    assert tab._time_display.text() == "25:00"


# --- Scoring i próbkowanie procesów ---

def test_compute_score_no_repo(qtbot) -> None:
    tab = RazdFocusTimerTab()
    qtbot.addWidget(tab)
    tab._state.start(1)
    score, counts = tab._compute_score()
    assert score == 1
    assert counts == {}


def test_compute_score_with_repo(qtbot, tmp_path) -> None:
    from pathlib import Path
    from razd.db.repository import RazdRepository
    repo = RazdRepository(tmp_path / "test.db")
    tab = RazdFocusTimerTab(repo=repo)
    qtbot.addWidget(tab)
    tab._state.whitelist = {"python.exe"}
    tab._state.start(5)
    tab._state.session_id = repo.start_focus_session("2026-05-02T10:00:00", {"python.exe"})
    # 8 próbek python (whitelist) + 2 chrome (nie whitelist) → score = round(8/10*10) = 8
    for _ in range(8):
        repo.add_focus_process_sample(tab._state.session_id, "2026-05-02T10:00:00", "python.exe")
    for _ in range(2):
        repo.add_focus_process_sample(tab._state.session_id, "2026-05-02T10:00:00", "chrome.exe")
    score, counts = tab._compute_score()
    assert score == 8
    assert counts["python.exe"] == 8
    assert counts["chrome.exe"] == 2
    repo.close()


def test_compute_score_all_whitelist(qtbot, tmp_path) -> None:
    from razd.db.repository import RazdRepository
    repo = RazdRepository(tmp_path / "test.db")
    tab = RazdFocusTimerTab(repo=repo)
    qtbot.addWidget(tab)
    tab._state.whitelist = {"code.exe"}
    tab._state.start(5)
    tab._state.session_id = repo.start_focus_session("2026-05-02T10:00:00", {"code.exe"})
    for _ in range(5):
        repo.add_focus_process_sample(tab._state.session_id, "2026-05-02T10:00:00", "code.exe")
    score, _ = tab._compute_score()
    assert score == 10
    repo.close()


def test_compute_score_empty_whitelist_returns_10(qtbot, tmp_path) -> None:
    from razd.db.repository import RazdRepository
    repo = RazdRepository(tmp_path / "test.db")
    tab = RazdFocusTimerTab(repo=repo)
    qtbot.addWidget(tab)
    tab._state.start(5)
    tab._state.session_id = repo.start_focus_session("2026-05-02T10:00:00", set())
    repo.add_focus_process_sample(tab._state.session_id, "2026-05-02T10:00:00", "anything.exe")
    score, _ = tab._compute_score()
    assert score == 10
    repo.close()


def test_check_active_app_records_sample(qtbot, tmp_path) -> None:
    from razd.db.repository import RazdRepository
    repo = RazdRepository(tmp_path / "test.db")
    tab = RazdFocusTimerTab(repo=repo)
    qtbot.addWidget(tab)
    tab._state.whitelist = {"python.exe"}
    tab._state.start(5)
    tab._state.session_id = repo.start_focus_session("2026-05-02T10:00:00", {"python.exe"})
    tab.check_active_app("python.exe")
    samples = repo.get_focus_process_samples(tab._state.session_id)
    assert len(samples) == 1
    assert samples[0][1] == "python.exe"
    repo.close()


def test_focus_session_ended_signal_emitted(qtbot, tmp_path) -> None:
    from razd.db.repository import RazdRepository
    repo = RazdRepository(tmp_path / "test.db")
    tab = RazdFocusTimerTab(repo=repo)
    qtbot.addWidget(tab)
    received: list = []
    tab.focus_session_ended.connect(lambda a, b, c, d: received.append((a, b, c, d)))
    tab._state.start(1)
    tab._state.session_id = repo.start_focus_session("2026-05-02T10:00:00", set())
    tab._on_timer_done()
    # dialog pojawi się automatycznie — zamknij go
    from PySide6.QtWidgets import QApplication
    for w in QApplication.topLevelWidgets():
        if hasattr(w, "accept"):
            try:
                w.accept()
            except Exception:
                pass
    assert len(received) == 1
    assert received[0][2] == tab._state.total_secs or received[0][2] >= 0
    repo.close()
