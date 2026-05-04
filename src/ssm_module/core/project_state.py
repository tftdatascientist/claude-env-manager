"""project_state.py — stan projektu SSS zrekonstruowany z SSS.jsonl."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BufferEntry:
    event_id: str
    timestamp: str
    target: str
    content: str
    status: str  # 'in_plan' | 'distributed'
    distributed_to: str = ''


@dataclass
class ProjectSnapshot:
    project_id: str
    current_round: Optional[str] = None  # 'dev' | 'service' | None
    current_session_id: Optional[str] = None
    session_count: int = 0
    next_count: int = 0
    done_count: int = 0
    buffer_entries: list[BufferEntry] = field(default_factory=list)
    repo_name: str = ''
    remote_url: str = ''
    last_script: str = ''
    last_event_timestamp: str = ''


def _jsonl_path(project_path: Path) -> Path:
    return project_path.resolve() / '.claude' / 'SSS.jsonl'


def fold_events(events: list[dict]) -> ProjectSnapshot:
    """Rekonstruuje stan projektu z listy eventów (fold left)."""
    if not events:
        return ProjectSnapshot(project_id='')

    project_id = events[0].get('project_id', '')
    snap = ProjectSnapshot(project_id=project_id)
    buffer_map: dict[str, BufferEntry] = {}

    for ev in events:
        t = ev.get('type', '')
        payload = ev.get('payload', {})
        ts = ev.get('timestamp', '')
        snap.last_event_timestamp = ts

        if t == 'session_start':
            snap.current_session_id = ev.get('session_id')
            snap.session_count += 1
            snap.current_round = None

        elif t == 'round_change':
            snap.current_round = ev.get('round')

        elif t == 'buffer_add':
            eid = ev.get('event_id', '')
            snap.current_round = ev.get('round') or snap.current_round
            buffer_map[eid] = BufferEntry(
                event_id=eid,
                timestamp=ts,
                target=payload.get('target', ''),
                content=payload.get('content', ''),
                status='in_plan',
            )

        elif t == 'buffer_distribute':
            target_file = payload.get('target_file', '')
            for be in buffer_map.values():
                if be.target == target_file and be.status == 'in_plan':
                    be.status = 'distributed'
                    be.distributed_to = target_file

        elif t == 'task_done':
            snap.done_count += 1

        elif t == 'script_run':
            snap.last_script = payload.get('script', '')
            snap.current_round = ev.get('round') or snap.current_round

        elif t == 'repo_finalized':
            snap.repo_name = payload.get('repo_name', '')
            snap.remote_url = payload.get('remote_url', '')

    snap.buffer_entries = list(buffer_map.values())
    return snap


def _sync_from_plan(snap: ProjectSnapshot, project_path: Path) -> None:
    """Aktualizuje next_count i done_count z PLAN.md."""
    plan = project_path.resolve() / 'PLAN.md'
    if not plan.exists():
        return
    try:
        text = plan.read_text(encoding='utf-8')
        import re
        m = re.search(r'<!-- SECTION:next -->(.*?)<!-- /SECTION:next -->', text, re.DOTALL)
        if m:
            snap.next_count = sum(
                1 for l in m.group(1).splitlines()
                if l.strip().lower().startswith('- [ ]')
            )
        m2 = re.search(r'<!-- SECTION:done -->(.*?)<!-- /SECTION:done -->', text, re.DOTALL)
        if m2:
            snap.done_count = sum(
                1 for l in m2.group(1).splitlines()
                if l.strip().lower().startswith('- [x]')
            )
    except Exception:
        pass


def load_snapshot(project_path: Path) -> ProjectSnapshot:
    """Wczytuje SSS.jsonl i zwraca aktualny snapshot."""
    import hashlib
    pid = hashlib.sha1(str(project_path.resolve()).lower().encode()).hexdigest()[:12]

    jsonl = _jsonl_path(project_path)
    raw_events: list[dict] = []
    if not jsonl.exists():
        snap = ProjectSnapshot(project_id=pid)
        _sync_from_plan(snap, project_path)
        return snap
    with open(jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw_events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    snap = fold_events(raw_events)
    _sync_from_plan(snap, project_path)
    return snap
