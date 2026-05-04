from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActivityType(str, Enum):
    DEEP_FOCUS = "Deep Focus"
    FOCUS = "Focus"
    WORK = "Work"
    CHILL = "Chill"
    AWAY = "Away"
    OFF = "Off"


# Hex color + alpha per activity
ACTIVITY_COLORS: dict[ActivityType, str] = {
    ActivityType.DEEP_FOCUS: "#7C3AED",
    ActivityType.FOCUS: "#A855F7",
    ActivityType.WORK: "#2563EB",
    ActivityType.CHILL: "#0D9488",
    ActivityType.AWAY: "#475569",
    ActivityType.OFF: "#1B2A3B",   # ciemny niebieski — widoczny na czarnym tle
}

ACTIVITY_ALPHA: dict[ActivityType, int] = {
    ActivityType.DEEP_FOCUS: 210,
    ActivityType.FOCUS: 180,
    ActivityType.WORK: 195,
    ActivityType.CHILL: 170,
    ActivityType.AWAY: 160,
    ActivityType.OFF: 200,
}

_SOCIAL_DOMAINS = frozenset({
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "fb.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "reddit.com",
    "twitch.tv",
})

_IDLE_AWAY_S = 300.0   # 5 min idle → Away
_GAP_OFF_S = 600.0     # 10 min gap between events → Off block inserted


@dataclass(frozen=True)
class ActivityBlock:
    start_ts: float
    end_ts: float
    activity: ActivityType


def _parse_ts(ts: str) -> float:
    try:
        return datetime.datetime.fromisoformat(ts).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _is_distraction(process_name: str | None, url: str | None, window_title: str | None) -> bool:
    if url:
        for domain in _SOCIAL_DOMAINS:
            if domain in url:
                return True
    if window_title:
        lower = window_title.lower()
        if any(s in lower for s in ("youtube", "facebook", "instagram", "tiktok", "twitter")):
            return True
    return False


def _in_focus_session(ts: float, focus_sessions: list[Any]) -> bool:
    for fs in focus_sessions:
        try:
            s = _parse_ts(fs.started_at)
            e = _parse_ts(fs.ended_at) if fs.ended_at else float("inf")
            if s <= ts < e:
                return True
        except AttributeError:
            pass
    return False


def _classify_one(ev: Any, ts: float, focus_sessions: list[Any]) -> ActivityType:
    idle_s = float(getattr(ev, "idle_seconds", 0))
    if getattr(ev, "event_type", "") == "idle" and idle_s >= _IDLE_AWAY_S:
        return ActivityType.AWAY

    in_focus = _in_focus_session(ts, focus_sessions)
    distraction = _is_distraction(
        getattr(ev, "process_name", None),
        getattr(ev, "url", None),
        getattr(ev, "window_title", None),
    )

    if in_focus:
        return ActivityType.DEEP_FOCUS if not distraction else ActivityType.FOCUS
    return ActivityType.CHILL if distraction else ActivityType.WORK


def classify_events(
    events: list[Any],
    focus_sessions: list[Any],
    now_ts: float | None = None,
) -> list[ActivityBlock]:
    """Classify a time-sorted list of events into ActivityBlocks."""
    if not events:
        return []
    if now_ts is None:
        now_ts = datetime.datetime.now().timestamp()

    blocks: list[ActivityBlock] = []

    for i, ev in enumerate(events):
        start_ts = _parse_ts(ev.ts)
        if start_ts == 0.0:
            continue

        end_ts = (
            _parse_ts(events[i + 1].ts)
            if i + 1 < len(events)
            else min(start_ts + 2.0, now_ts)
        )
        if end_ts <= start_ts:
            end_ts = start_ts + 2.0

        activity = _classify_one(ev, start_ts, focus_sessions)

        if end_ts - start_ts > _GAP_OFF_S:
            ev_end = start_ts + 2.0
            blocks.append(ActivityBlock(start_ts, ev_end, activity))
            blocks.append(ActivityBlock(ev_end, end_ts, ActivityType.OFF))
        else:
            blocks.append(ActivityBlock(start_ts, end_ts, activity))

    return _merge_consecutive(blocks)


def _merge_consecutive(blocks: list[ActivityBlock]) -> list[ActivityBlock]:
    if not blocks:
        return []
    merged = [blocks[0]]
    for b in blocks[1:]:
        prev = merged[-1]
        if prev.activity == b.activity and b.start_ts - prev.end_ts < 5.0:
            merged[-1] = ActivityBlock(prev.start_ts, b.end_ts, prev.activity)
        else:
            merged.append(b)
    return merged


def fill_gaps(
    blocks: list[ActivityBlock],
    window_start: float,
    window_end: float,
) -> list[ActivityBlock]:
    """
    Fills every gap in [window_start, window_end] with an OFF block.
    Always returns a contiguous list covering the full window.
    """
    sorted_blocks = sorted(blocks, key=lambda b: b.start_ts)
    result: list[ActivityBlock] = []
    cursor = window_start

    for block in sorted_blocks:
        bs = max(block.start_ts, window_start)
        be = min(block.end_ts, window_end)
        if be <= bs:
            continue
        if bs > cursor + 1.0:
            result.append(ActivityBlock(cursor, bs, ActivityType.OFF))
        result.append(ActivityBlock(bs, be, block.activity))
        cursor = max(cursor, be)

    if cursor < window_end - 1.0:
        result.append(ActivityBlock(cursor, window_end, ActivityType.OFF))

    return _merge_consecutive(result)
