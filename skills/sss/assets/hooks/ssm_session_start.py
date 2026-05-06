#!/usr/bin/env python3
"""ssm_session_start.py — hook SessionStart dla SSS.

Uruchamia się przy starcie każdej sesji CC w projekcie SSS.
Rejestruje event session_start w <projekt>/.claude/SSS.jsonl
oraz dopisuje projekt do ~/.ssm/projects.json (auto-wykrycie przez SSMService).

Protokół CC hooks:
- stdin: JSON z kontekstem sesji (lub pusty przy SessionStart)
- exit code 0 = success (nie blokuje startu sesji)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# events.py jest w tym samym katalogu co skrypty SSS skill
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / 'scripts'
sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import events
except ImportError:
    sys.exit(0)  # brak events.py — cicho, nie blokuj sesji

PLAN_MARKER = '<!-- SECTION:next -->'
_REGISTRY_PATH = Path(os.environ.get('USERPROFILE', Path.home())) / '.ssm' / 'projects.json'
_MAX_PROJECTS = 10


def is_sss_project(cwd: Path) -> bool:
    plan = cwd / 'PLAN.md'
    if not plan.exists():
        return False
    try:
        return PLAN_MARKER in plan.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return False


def _project_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).lower().encode()).hexdigest()[:12]


def register_in_ssm_registry(cwd: Path) -> None:
    """Dopisuje projekt do ~/.ssm/projects.json jeśli jeszcze go nie ma."""
    try:
        _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _REGISTRY_PATH.exists():
            data = json.loads(_REGISTRY_PATH.read_text(encoding='utf-8'))
        else:
            data = {}
        projects: list[dict] = data.get('projects', [])
        pid = _project_id(cwd)
        if any(p.get('project_id') == pid for p in projects):
            return  # już zarejestrowany
        if len(projects) >= _MAX_PROJECTS:
            return  # limit — nie dopisuj
        projects.append({
            'project_id': pid,
            'path': str(cwd.resolve()),
            'added_via': 'hook',
            'added_at': datetime.now(timezone.utc).astimezone().isoformat(),
            'name': cwd.name,
        })
        data['projects'] = projects
        _REGISTRY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass  # registry to nice-to-have — nie blokuj sesji


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    cwd = Path(os.environ.get('PWD', os.getcwd()))

    if not is_sss_project(cwd):
        return 0

    session_id = os.environ.get('SSM_SESSION_ID') or events.new_session_id()

    # Zapisz session_id do env-file żeby inne skrypty SSS mogły go odczytać
    ssm_env_file = cwd / '.claude' / '.ssm_session'
    try:
        ssm_env_file.parent.mkdir(parents=True, exist_ok=True)
        ssm_env_file.write_text(session_id, encoding='utf-8')
    except Exception:
        pass

    events.append_event(
        cwd, 'session_start', session_id,
        round=None,
        payload={
            'pid': os.getpid(),
            'cwd': str(cwd),
        },
    )

    # Rejestruj projekt w ~/.ssm/projects.json — SSMService wykryje go automatycznie
    register_in_ssm_registry(cwd)

    return 0


if __name__ == '__main__':
    sys.exit(main())
