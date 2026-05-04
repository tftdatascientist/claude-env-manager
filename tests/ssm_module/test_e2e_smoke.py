"""test_e2e_smoke.py — smoke test E2E: fake projekt SSS → plan_buffer.py add → SSS.jsonl."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path.home() / '.claude' / 'skills' / 'sss' / 'scripts'
_PYTHON = sys.executable


@pytest.fixture
def fake_sss_project(tmp_path: Path) -> Path:
    (tmp_path / '.claude').mkdir()
    (tmp_path / 'PLAN.md').write_text(
        '<!-- PLAN v2.0 -->\n'
        '## Buffer\n'
        '<!-- SECTION:buffer -->\n'
        '<!-- /SECTION:buffer -->\n'
        '## Next\n'
        '<!-- SECTION:next -->\n'
        '- [ ] task A\n'
        '<!-- /SECTION:next -->\n',
        encoding='utf-8',
    )
    return tmp_path


def test_e2e_plan_buffer_add_creates_event(fake_sss_project: Path) -> None:
    result = subprocess.run(
        [_PYTHON, str(_SCRIPTS_DIR / 'plan_buffer.py'), '--dir', str(fake_sss_project),
         'add', '--target', 'ARCHITECTURE.md', '--content', 'Decyzja: użyć JSONL'],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    jsonl = fake_sss_project / '.claude' / 'SSS.jsonl'
    assert jsonl.exists(), 'SSS.jsonl nie został utworzony'

    ev = json.loads(jsonl.read_text(encoding='utf-8').strip())
    assert ev['type'] == 'buffer_add'
    assert ev['payload']['target'] == 'ARCHITECTURE.md'
    assert ev['schema_version'] == 1
    assert len(ev['event_id']) == 36
