"""state.py — detekcja aktualnej fazy projektu DPS.

Zwraca JSON na stdout, którego AI używa żeby wybrać kolejny krok bez pytania usera.

Phases:
- init:        brak PLAN.md → trzeba zrobić Rundę Wstępną
- dev:         są zadania w next, bufor < 10 → kontynuuj Development
- service_due: bufor >= 10 LUB next pusty + done niepusty → triggeruj Serwis
- done:        next pusty + done pusty + bufor pusty → możliwe Zakończenie

Użycie:
    python state.py --target .
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parser as p  # noqa: E402


def count_lines(section_text: str, prefix: str = '- ') -> int:
    return sum(1 for l in section_text.splitlines() if l.strip().startswith(prefix))


def count_checkbox(section_text: str, checked: bool = False) -> int:
    marker = '- [x]' if checked else '- [ ]'
    return sum(
        1 for l in section_text.splitlines()
        if l.strip().lower().startswith(marker)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', default='.')
    args = ap.parse_args()

    target = Path(args.target)
    plan = target / 'PLAN.md'

    if not plan.exists():
        print(json.dumps({'phase': 'init', 'reason': 'brak PLAN.md'}))
        return

    text = p.read_file(plan)
    next_open = count_checkbox(p.read_section(text, 'next'), checked=False)
    done_count = count_checkbox(p.read_section(text, 'done'), checked=True)
    buffer_count = count_lines(p.read_section(text, 'buffer'))

    if buffer_count >= 10:
        phase = 'service_due'
        reason = f'bufor pełny ({buffer_count}/10)'
    elif next_open == 0 and (done_count > 0 or buffer_count > 0):
        phase = 'service_due'
        reason = 'next pusty + są rzeczy do uprzątnięcia'
    elif next_open == 0 and done_count == 0 and buffer_count == 0:
        phase = 'done'
        reason = 'wszystko puste — możliwe Zakończenie'
    else:
        phase = 'dev'
        reason = f'next: {next_open} otwartych, bufor: {buffer_count}/10'

    print(json.dumps({
        'phase': phase,
        'reason': reason,
        'next_open': next_open,
        'done_count': done_count,
        'buffer_count': buffer_count,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
