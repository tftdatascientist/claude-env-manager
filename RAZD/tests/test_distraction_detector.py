from __future__ import annotations

import datetime
import time

import pytest

from razd.tracker.distraction_detector import RazdDistractionDetector, WINDOW_S, ALERT_CONSECUTIVE
from razd.tracker.poller import EventDTO


def _dto(proc: str, event_type: str = "active", idle: float = 0.0) -> EventDTO:
    return EventDTO(
        ts=datetime.datetime.now().isoformat(),
        event_type=event_type,
        process_name=proc,
        window_title="Test",
        url=None,
        idle_seconds=idle,
    )


# --- Podstawowe liczenie przełączeń ---

def test_no_switch_on_same_process():
    det = RazdDistractionDetector(threshold=6.0)
    det.feed(_dto("code.exe"))
    det.feed(_dto("code.exe"))
    assert det.current_spm == 0.0


def test_switch_increments_counter():
    det = RazdDistractionDetector(threshold=6.0)
    det.feed(_dto("code.exe"))
    det.feed(_dto("chrome.exe"))
    assert det.current_spm > 0


def test_multiple_switches():
    det = RazdDistractionDetector(threshold=6.0)
    procs = ["code.exe", "chrome.exe", "slack.exe", "code.exe", "chrome.exe"]
    for p in procs:
        det.feed(_dto(p))
    assert det.current_spm > 0


# --- Sygnał score_updated ---

def test_score_updated_emitted_on_every_feed(qtbot):
    det = RazdDistractionDetector(threshold=6.0)
    scores = []
    det.score_updated.connect(lambda s: scores.append(s))
    det.feed(_dto("a.exe"))
    det.feed(_dto("b.exe"))
    det.feed(_dto("a.exe"))
    assert len(scores) == 3


# --- Alert ---

def test_distraction_alert_emitted_above_threshold(qtbot):
    det = RazdDistractionDetector(threshold=1.0)  # bardzo niski próg
    alerts = []
    det.distraction_alert.connect(lambda s: alerts.append(s))
    # generuj wiele przełączeń w krótkim czasie
    procs = ["a.exe", "b.exe"] * (ALERT_CONSECUTIVE + 2)
    for p in procs:
        det.feed(_dto(p))
    assert len(alerts) >= 1


def test_distraction_alert_not_emitted_below_threshold(qtbot):
    det = RazdDistractionDetector(threshold=100.0)  # bardzo wysoki próg
    alerts = []
    det.distraction_alert.connect(lambda s: alerts.append(s))
    for p in ["a.exe", "b.exe"] * 5:
        det.feed(_dto(p))
    assert len(alerts) == 0


def test_alert_not_repeated_while_above_threshold(qtbot):
    det = RazdDistractionDetector(threshold=1.0)
    alerts = []
    det.distraction_alert.connect(lambda s: alerts.append(s))
    procs = ["a.exe", "b.exe"] * 20
    for p in procs:
        det.feed(_dto(p))
    # alert emitowany tylko raz do czasu zejścia poniżej progu
    assert len(alerts) == 1


def test_alert_resets_when_below_threshold(qtbot):
    det = RazdDistractionDetector(threshold=1.0)
    alerts = []
    det.distraction_alert.connect(lambda s: alerts.append(s))

    # wywołaj alert
    for p in ["a.exe", "b.exe"] * (ALERT_CONSECUTIVE + 1):
        det.feed(_dto(p))
    assert len(alerts) == 1

    # zejdź poniżej progu (przestań przełączać)
    for _ in range(ALERT_CONSECUTIVE + 1):
        det.feed(_dto("a.exe"))  # brak przełączeń → spm spada do 0 (nie od razu — okno 60s)

    # reset ręczny
    det.reset()
    # teraz znowu można wygenerować alert
    for p in ["a.exe", "b.exe"] * (ALERT_CONSECUTIVE + 1):
        det.feed(_dto(p))
    assert len(alerts) == 2


# --- Idle event nie liczy przełączeń ---

def test_idle_event_does_not_count_as_switch():
    det = RazdDistractionDetector(threshold=6.0)
    det.feed(_dto("code.exe"))
    det.feed(_dto("", event_type="idle", idle=120.0))
    det.feed(_dto("code.exe"))
    # idle → process zmiana nie powinna liczyć (process_name pusty)
    assert det.current_spm == 0.0


# --- Reset ---

def test_reset_clears_state(qtbot):
    det = RazdDistractionDetector(threshold=1.0)
    alerts = []
    det.distraction_alert.connect(lambda s: alerts.append(s))
    for p in ["a.exe", "b.exe"] * (ALERT_CONSECUTIVE + 1):
        det.feed(_dto(p))
    det.reset()
    assert det.current_spm == 0.0
    assert det._above_threshold_count == 0
