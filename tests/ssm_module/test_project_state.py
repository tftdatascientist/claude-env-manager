"""test_project_state.py — testy fold_events i load_snapshot."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path.home() / '.claude' / 'skills' / 'sss' / 'scripts'
sys.path.insert(0, str(_SCRIPTS_DIR))
import events as ev_mod  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.ssm_module.core.project_state import fold_events, load_snapshot  # noqa: E402


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    (tmp_path / '.claude').mkdir()
    (tmp_path / 'PLAN.md').write_text(
        '<!-- SECTION:next -->\n- [ ] t1\n- [ ] t2\n<!-- /SECTION:next -->\n'
        '<!-- SECTION:done -->\n- [x] done1\n<!-- /SECTION:done -->', encoding='utf-8'
    )
    return tmp_path


def _make_event(type_: str, sid: str, round_: str | None = None, payload: dict | None = None, project_id: str = 'abc123456789') -> dict:
    return {
        'schema_version': 1,
        'event_id': 'e-' + type_,
        'timestamp': '2026-05-01T12:00:00+02:00',
        'type': type_,
        'session_id': sid,
        'project_id': project_id,
        'round': round_,
        'payload': payload or {},
    }


def test_fold_events_session_start() -> None:
    sid = 'test-session-id'
    evs = [_make_event('session_start', sid)]
    snap = fold_events(evs)
    assert snap.session_count == 1
    assert snap.current_session_id == sid


def test_fold_events_buffer_add_and_distribute() -> None:
    sid = 'sid'
    evs = [
        _make_event('session_start', sid),
        {**_make_event('buffer_add', sid, round_='dev', payload={'target': 'ARCHITECTURE.md', 'content': 'decyzja X'}), 'event_id': 'e-buf1'},
        _make_event('buffer_distribute', sid, round_='service', payload={'target_file': 'ARCHITECTURE.md', 'section': 'decisions', 'count': 1}),
    ]
    snap = fold_events(evs)
    assert len(snap.buffer_entries) == 1
    assert snap.buffer_entries[0].status == 'distributed'
    assert snap.buffer_entries[0].distributed_to == 'ARCHITECTURE.md'


def test_fold_events_repo_finalized() -> None:
    sid = 'sid'
    evs = [
        _make_event('session_start', sid),
        _make_event('repo_finalized', sid, payload={'repo_name': 'my-repo', 'remote_url': 'https://github.com/x/my-repo'}),
    ]
    snap = fold_events(evs)
    assert snap.repo_name == 'my-repo'
    assert snap.remote_url == 'https://github.com/x/my-repo'


def test_load_snapshot_reads_plan_md(fake_project: Path) -> None:
    snap = load_snapshot(fake_project)
    assert snap.next_count == 2
    assert snap.done_count == 1
