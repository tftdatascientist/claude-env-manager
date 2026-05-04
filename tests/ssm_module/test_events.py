"""test_events.py — testy events.py z SSS skill."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# events.py żyje w globalnym ~/.claude/skills/sss/scripts/
_SCRIPTS_DIR = Path.home() / '.claude' / 'skills' / 'sss' / 'scripts'
sys.path.insert(0, str(_SCRIPTS_DIR))
import events  # noqa: E402


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    (tmp_path / '.claude').mkdir()
    (tmp_path / 'PLAN.md').write_text(
        '<!-- SECTION:next -->\n- [ ] task\n<!-- /SECTION:next -->', encoding='utf-8'
    )
    return tmp_path


def test_events_append_basic(fake_project: Path) -> None:
    sid = events.new_session_id()
    ev = events.append_event(fake_project, 'session_start', sid, round=None, payload={'pid': 1})

    assert ev['schema_version'] == events.EVENTS_API_VERSION
    assert len(ev['event_id']) == 36
    assert len(ev['project_id']) == 12
    assert 'T' in ev['timestamp']
    assert ev['type'] == 'session_start'
    assert ev['session_id'] == sid
    assert ev['round'] is None
    assert ev['payload']['pid'] == 1


def test_events_jsonl_file_created(fake_project: Path) -> None:
    sid = events.new_session_id()
    events.append_event(fake_project, 'buffer_add', sid, round='dev', payload={'target': 'ARCHITECTURE.md', 'content': 'test'})

    jsonl = fake_project / '.claude' / 'SSS.jsonl'
    assert jsonl.exists()
    line = json.loads(jsonl.read_text(encoding='utf-8').strip())
    assert line['type'] == 'buffer_add'
    assert line['payload']['target'] == 'ARCHITECTURE.md'


def test_events_read_events(fake_project: Path) -> None:
    sid = events.new_session_id()
    events.append_event(fake_project, 'session_start', sid, round=None)
    events.append_event(fake_project, 'buffer_add', sid, round='dev', payload={'target': 'CLAUDE.md', 'content': 'x'})

    result = events.read_events(fake_project)
    assert len(result) == 2
    assert result[0]['type'] == 'session_start'
    assert result[1]['type'] == 'buffer_add'


def test_events_read_events_skips_bad_lines(fake_project: Path) -> None:
    jsonl = fake_project / '.claude' / 'SSS.jsonl'
    jsonl.write_text('{"type":"session_start","schema_version":1,"event_id":"x","timestamp":"t","session_id":"s","project_id":"p","round":null,"payload":{}}\nBAD LINE\n', encoding='utf-8')
    result = events.read_events(fake_project)
    assert len(result) == 1
