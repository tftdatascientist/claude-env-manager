#!/usr/bin/env python3
"""buffer_monitor.py — hook PostToolUse dla SSS.

Uruchamia się po każdej operacji Write/Edit na pliku PLAN.md w projekcie DPS.
Sprawdza liczbę wpisów w sekcji `buffer` i jeśli >= 10 — emituje hint do Claude'a
przez stdout (Claude Code zbiera ten output do kontekstu następnej tury).

Komunikuje się przez Claude Code hooks JSON protocol:
- stdin: JSON z `{tool_name, tool_input, tool_response, ...}`
- stdout: tekst, który Claude zobaczy w następnej turze
- exit code 0 = success
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path


SECTION_RE_TMPL = (
    r'<!--\s*SECTION:{name}\s*-->(.*?)<!--\s*/SECTION:{name}\s*-->'
)


def read_section(text: str, name: str) -> str:
    pattern = SECTION_RE_TMPL.format(name=re.escape(name))
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ''


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # cicho, bez blokady

    tool_name = payload.get('tool_name', '')
    plan_path: Path | None = None

    if tool_name in ('Write', 'Edit', 'MultiEdit'):
        # bezpośrednia edycja PLAN.md przez Claude'a
        tool_input = payload.get('tool_input', {}) or {}
        file_path = tool_input.get('file_path') or tool_input.get('path') or ''
        if not file_path.endswith('PLAN.md'):
            return 0
        candidate = Path(file_path)
        if not candidate.is_file():
            return 0
        plan_path = candidate

    elif tool_name == 'Bash':
        # zapis bufora przez plan_buffer.py — hook nie widzi tego jako Edit,
        # więc łapiemy po nazwie skryptu w komendzie i znajdujemy PLAN.md przez cwd
        cmd = (payload.get('tool_input', {}) or {}).get('command', '') or ''
        if 'plan_buffer.py' not in cmd or ' add' not in cmd:
            return 0
        cwd = payload.get('cwd', '.') or '.'
        candidate = Path(cwd) / 'PLAN.md'
        if not candidate.is_file():
            return 0
        plan_path = candidate

    else:
        return 0

    try:
        text = plan_path.read_text(encoding='utf-8')
    except Exception:
        return 0

    buf = read_section(text, 'buffer')
    next_sec = read_section(text, 'next')
    count = sum(1 for l in buf.splitlines() if l.strip().startswith('- '))
    next_open = sum(
        1 for l in next_sec.splitlines()
        if l.strip().lower().startswith('- [ ]')
    )

    msgs = []
    if count >= 10:
        msgs.append(
            f'[SSS] Bufor PLAN.md osiągnął {count}/10 wpisów. '
            'STOP development — uruchom /ser przed kolejnymi zmianami.'
        )
    elif count >= 8:
        msgs.append(
            f'[SSS] Bufor PLAN.md: {count}/10 — zbliżasz się do progu Rundy Serwisowej.'
        )

    if next_open == 0:
        msgs.append(
            '[SSS] Sekcja `next` w PLAN.md jest pusta. '
            'Po skończeniu bieżącego zadania uruchom /ser.'
        )

    if msgs:
        # Claude Code czyta stdout z hooka i włącza go do kontekstu
        print('\n'.join(msgs))

    return 0


if __name__ == '__main__':
    sys.exit(main())
